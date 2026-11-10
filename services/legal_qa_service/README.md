# Legal QA

Ядро использует неизменяемые файловые снимки, текстовый поиск и OpenAI-совместимый прокси. Сервис и автономный сабмит вызывают общий обработчик ответа. Системные инструкции отделены от недоверенных данных. Генератор возвращает структурированные утверждения, после чего проверяются исход, ID, точность цитат, числовые факты и смысловая поддержка отдельным вызовом модели. Финальный текст собирается из принятых утверждений; отдельный свободный текст черновика не используется. Модельная проверка не гарантирует истинность или полноту.

## Установка и запуск

Из корня проекта:

```sh
uv sync --locked --project services/legal_qa_service
uv run --locked --project services/legal_qa_service python -m legal_qa /path/knowledge-base.zip --catalog /tmp/legal-catalog
```

Для gRPC задать `LEGAL_QA_CATALOG`, различные `GATEWAY_LEGAL_QA_RPC_TOKEN` и `CONVERSATION_LEGAL_QA_RPC_TOKEN`, а также параметры модели. Запуск:

```sh
uv run --locked --project services/legal_qa_service python -m legal_qa.transport.grpc_server
```

Адрес `LEGAL_QA_GRPC_ADDRESS` по умолчанию `[::]:50051`. База `meridian` возвращается каталогом; клиент использует полученный ID. Gateway читает каталог и источники; Conversation читает каталог и вызывает Answer. Health Check перепроверяет целостность активного снимка. Внутренний сервер рассчитан на закрытую сеть Compose. Схема снимка 2 содержит стабильные ссылки изменений; загрузчик также открывает схему 1. Старые снимки сохраняются.

## Модель и ограничения

`LLM_BASE_URL`/`OPENAI_BASE_URL`, `LLM_API_KEY`/`OPENAI_API_KEY`, `LLM_MODEL`/`OPENAI_MODEL`/`GEN_MODEL` обязательны для сетевых вызовов. `/v1` в базовом URL сохраняется. `TEMPERATURE` по умолчанию 0, `MAX_TOKENS` 2048 на вызов. `MAX_WORKERS` по умолчанию 4, максимум 8 — одновременно выполняемые сетевые вызовы и строки CSV. Генерация и проверка делят deadline, технические сбои не классифицируются как отсутствие нормы. Допускается один повтор транспорта и один новый черновик после отклонения. Сторонний резерв не настроен. Эмбеддинги и реранжирование не используются.

Даты имеют роль, происхождение и точность. Поддержаны цифровые, ISO, словесные даты и месячные интервалы. Выбор редакции, замена адреса и дополнение К-12 меняют доказательства до генерации. Для закона наблюдаемый текст доступен на 10.10.2026; иной период без подтверждённой редакции не предполагается. Разбор естественного языка и разметка редакционных пояснений остаются эвристическими; сложные формулировки требуют дополнительной приёмки. Оценка реальной модели не выполнена.

## Сабмит

```sh
python services/legal_qa_service/build_submission.py /tmp/jurion-submission.zip
```

Сборщик генерирует корневые модули из общего ядра. В архиве нет корпуса, вопросов, веба, gRPC и ключей. Пустой requirements соответствует использованию стандартной библиотеки. После распаковки:

```sh
DATA_DIR=/path/data python solution.py
```

Вход: `questions.csv` и `knowledge-base.zip`; по умолчанию каталог `data`. Выход в текущем каталоге — `submission.csv`, ID строковые, порядок сохранён. Контекст отдельный для каждой строки. Ответ не обрезается срезом: превышение 10000 символов считается техническим сбоем. Общий бюджет 19 минут. Размер неизвестного полного набора и пиковая память не измерены.

## Проверки

```sh
uv run --locked --project services/legal_qa_service python -m unittest discover -s services/legal_qa_service/tests -v
# Обязательные синтетические регрессии без личных файлов:
uv run --locked --project services/legal_qa_service python -m unittest discover -s services/legal_qa_service/tests -p test_final.py -v
# Явный режим предоставленного корпуса (отсутствующий вход — ошибка):
uv run --locked --project services/legal_qa_service python services/legal_qa_service/evaluate.py --corpus /path/knowledge-base.zip --questions /path/questions.csv --output /tmp/evidence.json
# Будущая модель; параметры прокси задаются окружением:
uv run --locked --project services/legal_qa_service python services/legal_qa_service/evaluate.py --corpus /path/knowledge-base.zip --questions /path/questions.csv --output /tmp/answers.json --real-model
```

Изолированный ZIP проверяется отдельным процессом с `-S`, без PYTHONPATH и установленных пакетов проекта, через настоящий локальный HTTP-провайдер. Выходные файлы оценки хранить вне Git. Статусы и оставшиеся пробелы — в `docs/validation/final-backend.md`.
