# API веб-чата юридического ассистента

Контракт MVP для фронтенда. Браузер работает с Gateway по HTTP/JSON. Поля описывают интерфейс, а внутренняя реализация определена в [ТЗ по сервисам](tasks/README.md).

## Общие правила

- Базовый путь — `/api/v1`. Фронтенд использует относительные URL. При локальной разработке проксируем этот путь на бэкенд.
- Тела запросов и ответы API передаются как `application/json`. Исключение — получение оригинала источника.
- ID — непрозрачные строки. Время передаётся в UTC в формате `2026-11-10T16:30:00Z`. Дата события передаётся отдельно в формате `YYYY-MM-DD`, без часового пояса.
- Защищённые маршруты принимают `Authorization: Bearer <access_token>`. Вход и обновление токенов описаны ниже. Диалоги принадлежат пользователю Identity и доступны после повторного входа.
- `text`, тексты цитат и документы показываем как текст. Для переносов строк подходит `white-space: pre-wrap`.

Все пути в таблицах указаны относительно `/api/v1`.

| Метод и путь | Назначение | Успешный ответ |
| --- | --- | --- |
| `POST /auth/register` | Зарегистрировать юриста и войти | `201` · `AuthResponse` и refresh cookie |
| `POST /auth/login` | Войти | `200` · `AuthResponse` и refresh cookie |
| `POST /auth/refresh` | Обновить токены | `200` · `AccessTokenResponse` и новая refresh cookie |
| `POST /auth/logout` | Выйти | `204` · очистка refresh cookie |
| `GET /auth/me` | Получить профиль вошедшего пользователя | `200` · `{ user: UserSnapshot }` |
| `GET /knowledge-bases` | Получить доступные базы | `200` · `{ items: KnowledgeBase[] }` |
| `POST /conversations` | Создать диалог в выбранной базе | `201` · `Conversation` |
| `GET /conversations` | Получить список диалогов | `200` · `ConversationPage` |
| `GET /conversations/{conversation_id}/messages` | Открыть историю диалога | `200` · `MessagePage` |
| `POST /conversations/{conversation_id}/messages` | Отправить вопрос или ответить на уточнение | `200` или `202` · `AnswerRun` |
| `GET /runs/{run_id}` | Получить состояние попытки и её результат | `200` · `AnswerRun` |
| `POST /runs/{run_id}/retry` | Повторить неудачную попытку для той же реплики | `200` или `202` · `AnswerRun` |
| `GET /sources/{snapshot_id}/chunks/{chunk_id}` | Открыть фрагмент с реквизитами источника | `200` · `SourceChunk` |
| `GET /sources/{snapshot_id}/files/{file_id}` | Получить оригинал источника | `200` · `text/plain; charset=utf-8` для TXT |

## Вход и токены

| Маршрут | Тело HTTP | Аутентификация |
| --- | --- | --- |
| `POST /auth/register` | `{email, nickname, password}` | Без токена. Identity присваивает роль `lawyer` |
| `POST /auth/login` | `{email, password}` | Без токена |
| `POST /auth/refresh` | Без тела | Refresh cookie |
| `POST /auth/logout` | `{all_sessions?: boolean}` или без тела | Refresh cookie для текущей сессии. При `all_sessions: true` обязателен access JWT |
| `GET /auth/me` | Без тела | Access JWT |

```ts
type UserSnapshot = {
  user_id: string;
  email: string;
  nickname: string;
  role: "lawyer" | "admin";
  status: "active" | "blocked" | "deleted";
  created_at: string;
  updated_at: string;
};

type AccessTokenResponse = {
  access_token: string;
  access_token_expires_at: string;
};

type AuthResponse = AccessTokenResponse & { user: UserSnapshot };
```

Gateway устанавливает refresh cookie `jurion_refresh` с `HttpOnly`, `SameSite=Lax`, путём `/api/v1/auth` и `Secure` на HTTPS. Refresh token не приходит в JSON. Веб работает same-origin. Браузер сам отправляет cookie. Access token храним в памяти приложения.

После перезагрузки фронт может выполнить `POST /auth/refresh`, получить access token и запросить `GET /auth/me`. Если токен истёк во время запроса, выполняем один refresh и повторяем исходный запрос. Параллельные запросы используют один общий refresh, поскольку успешная ротация делает старый refresh недействительным. Для отправки вопроса и retry повтор сохраняет прежний `Idempotency-Key`. При `REFRESH_INVALID` показываем вход. При временном сбое сохраняем состояние интерфейса и предлагаем повтор.

## Базы, диалоги и история

`GET /knowledge-bases` в MVP возвращает одну базу. Если доступна только одна, фронт может выбрать её автоматически.

```json
{
  "items": [
    { "id": "meridian", "title": "Корпус ООО «Меридиан»" }
  ]
}
```

Для `POST /conversations` отправляем `{"knowledge_base_id":"meridian"}`. Поле обязательное; используйте непрозрачный ID из GET /knowledge-bases, не хардкодите пример.

```json
{
  "id": "conv_01",
  "knowledge_base_id": "meridian",
  "title": "Новый диалог",
  "created_at": "2026-11-10T16:30:00Z",
  "updated_at": "2026-11-10T16:30:00Z"
}
```

`GET /conversations?limit=20&cursor=…` возвращает диалоги от недавно обновлённых к старым. `limit` по умолчанию 20, максимум 50. Для первой страницы `cursor` опускаем. Следующее значение берём из `next_cursor`, при `null` страниц больше нет. Заголовок чата может обновиться после первого вопроса, поэтому для списка используем заголовок из ответа сервера.

`GET /conversations/{conversation_id}/messages?limit=30` возвращает последние 30 реплик. Элементы внутри страницы идут по возрастанию `seq`. Для более старой страницы передаём `before_seq` со значением `next_before_seq` из предыдущей страницы. Сервер возвращает реплики со строго меньшим `seq`. При `null` история загружена целиком. `limit` по умолчанию 30, максимум 100.

```ts
type KnowledgeBase = { id: string; title: string };

type Conversation = {
  id: string;
  knowledge_base_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type ConversationPage = {
  items: Conversation[];
  next_cursor: string | null;
};

type MessagePage = {
  conversation: Conversation;
  items: Message[];
  next_before_seq: number | null;
  latest_run_id: string | null;
};
```

`latest_run_id` указывает на последнюю принятую попытку в диалоге. Если при открытии истории последняя реплика пользователя осталась без ответа, фронт может получить состояние через `GET /runs/{run_id}` и восстановить ожидание или кнопку повтора.

## Отправка сообщения

`POST /conversations/{conversation_id}/messages` принимает `text` и необязательное `as_of_date`. Пример для обычного вопроса.

```http
POST /api/v1/conversations/conv_01/messages
Content-Type: application/json
Authorization: Bearer <access_token>
Idempotency-Key: e8bd1e40-d076-46d0-8f53-4abb605ab184
```

```json
{
  "text": "Какая арендная плата по договору с ООО «Северный Склад»?"
}
```

- `text` должен содержать от 1 до 8 000 символов после удаления пробелов по краям.
- `as_of_date` опускаем, если пользователь не выбрал конкретную дату в интерфейсе. Если дата известна, можно передать `"as_of_date": "2024-08-15"`. Даты, написанные в самом вопросе, остаются в `text`.
- История берётся по ID диалога. Ответ на уточнение отправляется тем же методом в тот же диалог.
- `Idempotency-Key` обязателен. Для новой отправки фронт создаёт новый UUID. При повторной отправке после обрыва соединения использует тот же ключ и то же тело. Повтор с этим ключом возвращает состояние исходной попытки и сохраняет ID реплики. Если тело изменилось, сервер отвечает `409 IDEMPOTENCY_CONFLICT`.
- Одновременно в диалоге выполняется одна попытка. Новая отправка с другим ключом во время обработки получает `409 RUN_IN_PROGRESS` с ID текущей попытки. Во время ожидания можно просматривать историю и источники.

### Состояния попытки

```ts
type MessageBase = {
  id: string;
  seq: number;
  text: string;
  created_at: string;
};

type UserMessage = MessageBase & { role: "user" };

type AssistantMessage = MessageBase & {
  role: "assistant";
  answer: Answer;
};

type Message = UserMessage | AssistantMessage;

type RunBase = {
  run_id: string;
  conversation_id: string;
  user_message: UserMessage;
};

type AnswerRun = RunBase & (
  | { state: "running"; assistant_message: null; error: null }
  | { state: "completed"; assistant_message: AssistantMessage; error: null }
  | { state: "failed"; assistant_message: null; error: ApiError }
);
```

| Ситуация | Что получает фронт | Что показать |
| --- | --- | --- |
| Ответ уже готов | `POST` возвращает `200` с `state: "completed"` | Реплику ассистента с цитатами или пояснением |
| Вопрос принят, ответ готовится | `POST` возвращает `202` с `state: "running"` | Реплику пользователя и индикатор ожидания. Запрашивать `GET /runs/{run_id}` примерно раз в секунду до конечного состояния |
| Обработка завершилась технической ошибкой | При повторе `POST` возможен `502`, `503` или `504` с `error.run_id`. `GET /runs/{run_id}` возвращает `200` с `state: "failed"` и `error` | Ошибку рядом с вопросом. Кнопку «Повторить» показывать, когда `error.retryable` равно `true` |

Если соединение оборвалось до получения `run_id`, повторяем исходный `POST` с прежним ключом. При отображении данных из ответа и истории объединяем реплики по `id`, сортируем по `seq`.

`POST /runs/{run_id}/retry` вызывается для последней неудачной попытки с `retryable: true`. Запрос отправляется без тела и с новым `Idempotency-Key`. Он создаёт новый `run_id` для исходной реплики с тем же `user_message.id`. Если попытка уже заменена или диалог продолжился, сервер возвращает `409 RETRY_NOT_AVAILABLE`. Сетевой повтор самого запроса на повтор использует уже выданный ему ключ.

### Готовый ответ

```ts
type Outcome =
  | "answered"
  | "partially_answered"
  | "needs_clarification"
  | "insufficient_evidence"
  | "invalid_premise"
  | "out_of_scope"
  | "disallowed";

type Answer = {
  outcome: Outcome;
  snapshot_id: string;
  claims: Claim[];
  missing_information: string[];
  clarification_question: string | null;
};

type Claim = {
  id: string;
  text: string;
  citations: Citation[];
};

type Citation = {
  chunk_id: string;
  label: string;
  quote: string;
};
```

Пример `200` после вопроса про арендную плату.

```json
{
  "run_id": "run_01",
  "conversation_id": "conv_01",
  "state": "completed",
  "user_message": {
    "id": "msg_01",
    "seq": 1,
    "role": "user",
    "text": "Какая арендная плата по договору с ООО «Северный Склад»?",
    "created_at": "2026-11-10T16:30:05Z"
  },
  "assistant_message": {
    "id": "msg_02",
    "seq": 2,
    "role": "assistant",
    "text": "Арендная плата составляет 450 000 рублей в месяц, включая НДС.",
    "created_at": "2026-11-10T16:30:07Z",
    "answer": {
      "outcome": "answered",
      "snapshot_id": "snap_01",
      "claims": [
        {
          "id": "claim_01",
          "text": "450 000 рублей в месяц, включая НДС.",
          "citations": [
            {
              "chunk_id": "chunk_a08_3_1",
              "label": "Договор А-08/2024, п. 3.1",
              "quote": "Арендная плата составляет 450 000 (четыреста пятьдесят тысяч) рублей в месяц, включая НДС."
            }
          ]
        }
      ],
      "missing_information": [],
      "clarification_question": null
    }
  },
  "error": null
}
```

Основной текст сообщения — `assistant_message.text`. Блок источников группируем по `claims`. Если один вывод опирается на несколько документов, показываем все его цитаты. Дополнительные поля могут использоваться для отдельного блока «Чего не хватает» и уточняющего вопроса.

| `outcome` | Как отобразить |
| --- | --- |
| `answered` | Ответ с основаниями |
| `partially_answered` | Подтверждённую часть и недостающие сведения |
| `needs_clarification` | Уточняющий вопрос. Можно сразу ответить в этом чате |
| `insufficient_evidence` | Пояснение, каких данных или редакции документа не хватает |
| `invalid_premise` | Исправление предпосылки и источники при наличии |
| `out_of_scope` | Пояснение о тематике ассистента |
| `disallowed` | Обоснованный отказ и допустимый вариант помощи, если он есть |

Все эти исходы — `state: "completed"`. Для ответа без подтверждённых выводов `claims` может быть пустым. Если уточнение уже присутствует в `text`, достаточно показать его один раз.

## Источники

При клике на цитату используем `answer.snapshot_id` из конкретного ответа и `citation.chunk_id` из выбранной цитаты. Снимок нужен, чтобы открыть ту же редакцию после обновления базы.

`GET /sources/snap_01/chunks/chunk_a08_3_1` возвращает `SourceChunk`.

```ts
type SourceChunk = {
  chunk_id: string;
  snapshot_id: string;
  document_title: string;
  version_label: string | null;
  provision_label: string | null;
  text: string;
  line_start: number;
  line_end: number;
  file: {
    id: string;
    name: string;
    media_type: string;
    url: string;
  };
};
```

```json
{
  "chunk_id": "chunk_a08_3_1",
  "snapshot_id": "snap_01",
  "document_title": "Договор аренды нежилого помещения № А-08/2024",
  "version_label": "От 01.08.2024",
  "provision_label": "п. 3.1",
  "text": "3.1. Арендная плата составляет 450 000 (четыреста пятьдесят тысяч) рублей в месяц, включая НДС.",
  "line_start": 14,
  "line_end": 14,
  "file": {
    "id": "file_a08",
    "name": "Договор аренды А-08-2024 Северный Склад.txt",
    "media_type": "text/plain",
    "url": "/api/v1/sources/snap_01/files/file_a08"
  }
}
```

`line_start` и `line_end` — номера строк оригинала с единицы, обе границы включены. В панели показываем `text`. По кнопке «Открыть оригинал» фронт запрашивает `file.url` с тем же заголовком `Authorization`, затем отображает полученный текст и может выделить нужные строки. Для скачивания можно создать локальный Blob из ответа. Токен в URL не передаётся.

## Ошибки API

Тело ответа вне `2xx` содержит `{ "error": ApiError }`. То же описание ошибки возвращается в `AnswerRun.error` при `state: "failed"`.

```ts
type ApiError = {
  code: string;
  message: string;
  retryable: boolean;
  run_id?: string;
  field_errors?: { field: string; message: string }[];
};
```

Пример `409` при параллельной отправке в тот же диалог.

```json
{
  "error": {
    "code": "RUN_IN_PROGRESS",
    "message": "Предыдущий вопрос ещё обрабатывается.",
    "retryable": false,
    "run_id": "run_01"
  }
}
```

| HTTP | `error.code` | Действие фронта |
| --- | --- | --- |
| `401` | `AUTH_REQUIRED` | Один раз обновить access token или показать вход |
| `401` | `INVALID_CREDENTIALS` | Показать ошибку входа |
| `401` | `REFRESH_INVALID` | Показать форму входа |
| `403` | `FORBIDDEN` | Показать отсутствие доступа |
| `404` | `NOT_FOUND` | Показать, что чат, попытка или источник недоступны |
| `409` | `RUN_IN_PROGRESS` | Загрузить текущую попытку по `error.run_id` |
| `409` | `IDEMPOTENCY_CONFLICT` | Сообщить об ошибке отправки. Для изменённого вопроса использовать новый ключ |
| `409` | `RETRY_NOT_AVAILABLE` | Обновить историю. Повтор для этой попытки больше недоступен |
| `409` | `EMAIL_ALREADY_EXISTS` | Предложить войти с этим email |
| `413` | `PAYLOAD_TOO_LARGE` | Сохранить черновик и предложить сократить запрос |
| `422` | `VALIDATION_ERROR` | Подсветить поля из `field_errors` и сохранить введённый текст |
| `429` | `RATE_LIMITED` | Предложить повторить позже. Учитывать `Retry-After`, если сервер его вернул |
| `502` | `UPSTREAM_ERROR` | Показать техническую ошибку. Если есть `run_id`, загрузить состояние попытки |
| `503` | `MODEL_UNAVAILABLE` | При наличии `run_id` загрузить состояние попытки. Иначе повторить исходную отправку с прежним ключом после паузы |
| `503` | `SERVICE_UNAVAILABLE` | Показать временную недоступность. При повторе отправки сохранить ключ |
| `504` | `ANSWER_TIMEOUT` | Загрузить состояние попытки по `run_id` и показать возможность повтора согласно `retryable` |
| `504` | `UPSTREAM_TIMEOUT` | При неопределённом результате отправки повторить её с прежним ключом |

Для неизвестного кода и сетевого сбоя показываем общую техническую ошибку, сохраняя введённый вопрос. Сбой при открытии источника показываем в панели источника, чтобы ответ оставался доступен.

## Что покрыть моками

1. Вход, создание диалога, отправка вопроса, готовый ответ с цитатой и открытие источника.
2. Ответ через `202`, затем `GET /runs/{id}` с `running` и `completed`.
3. `needs_clarification` и следующая реплика в том же диалоге.
4. `partially_answered` с цитатой и списком недостающих данных. `insufficient_evidence` с пустым списком цитат.
5. Технический сбой и повтор с тем же `user_message.id`.
6. Перезагрузка страницы во время ожидания. После refresh история и состояние восстанавливаются через `latest_run_id`.

### Примеры исходов Legal QA

Ниже только форма поля `answer`; реальные `snapshot_id`, `chunk_id` и ссылки берутся из ответа сервера. При создании диалога ID базы берётся из `GET /api/v1/knowledge-bases`.

```json
{"outcome":"answered","text":"Арендная плата — 450 000 рублей в месяц, не позднее 5-го числа.","claims":[{"text":"Арендная плата — 450 000 рублей в месяц.","citations":[{"chunk_id":"<opaque-chunk-id>","label":"Договор аренды, п. 3.1","quote":"<exact-source-text>"}]}],"missing_information":[],"snapshot_id":"<opaque-snapshot-id>"}
```

```json
{"outcome":"partially_answered","text":"Подтверждена сумма оплаты. Для определения срока не хватает применимого пункта.","claims":[{"text":"Подтверждена сумма оплаты.","citations":[{"chunk_id":"<opaque-chunk-id>","label":"Договор, пункт об оплате","quote":"<exact-source-text>"}]}],"missing_information":["Применимый пункт о сроке оплаты"],"snapshot_id":"<opaque-snapshot-id>"}
```

```json
{"outcome":"needs_clarification","text":"Когда подписана спецификация на партию?","claims":[],"missing_information":["Дата подписания спецификации"],"clarification_question":"Когда подписана спецификация на партию?","snapshot_id":"<opaque-snapshot-id>"}
```

Технический сбой принятой попытки возвращается в `AnswerRun`, а не как бизнес-исход ответа:

```json
{"state":"failed","error":{"code":"MODEL_UNAVAILABLE","message":"Model unavailable","retryable":true},"assistant_message":null}
```
