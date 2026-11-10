# JURION

JURION — сервис юридического чата. Браузер работает через Gateway; Identity, Conversation, Legal QA и две независимые PostgreSQL доступны только во внутренней сети Compose. Текущий контракт: [API](docs/api.md), [план интеграции](docs/tasks/README.md).

## Локальный запуск Compose

Нужны Docker с Compose v2, OpenSSL и предоставленный архив корпуса. Для тестового запуска используйте **новые** ключи и токены: они не должны совпадать с Casino Platform. Из корня проекта:

```sh
cp .env.example .env
mkdir -p .local
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out .local/jurion-private.pem
openssl pkey -in .local/jurion-private.pem -pubout -out .local/jurion-public.pem
chmod 600 .local/jurion-private.pem
```

Укажите в `.env` абсолютный путь к архиву в `LEGAL_QA_ARCHIVE`, адрес и данные доступного OpenAI-совместимого провайдера в `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. Замените два пароля БД и все четыре служебных токена уникальными случайными значениями. Для паролей БД используйте URL-safe символы, например `openssl rand -hex 32`, поскольку пароль входит в строку подключения. Значения примеров предназначены только для изолированной локальной разработки. Для локального HTTP установлено `REFRESH_COOKIE_SECURE=false`; при HTTPS измените на `true` и задайте правильный `PUBLIC_ORIGIN`.

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl -fsS http://localhost:8000/health/live
curl -fsS http://localhost:8000/health/ready
```

`up` создаёт отдельные тома `jurion_identity_data`, `jurion_conversation_data`, `jurion_legal_catalog`; выполняет миграции Identity и Conversation до запуска сервисов и импортирует корпус перед Legal QA. При повторном запуске сохранённый активный снимок проверяется, но не заменяется автоматически: так не откатывается ранее опубликованный снимок. Ошибка проверки прерывает запуск. Для явной публикации нового архива обновите `LEGAL_QA_ARCHIVE`, затем:

```sh
docker compose run --rm --no-deps legal_qa_import python -m legal_qa /input/knowledge-base.zip --catalog /data/catalog
```

Старые снимки и исходники остаются в каталоге: цитаты в существующих ответах продолжают ссылаться на свои редакции. `docker compose down` останавливает проект и сохраняет данные. Не используйте `down --volumes`, если нужны данные.

Gateway по умолчанию публикует только `127.0.0.1:8000` (управляется `GATEWAY_BIND_ADDRESS` и `GATEWAY_PORT`); gRPC, БД и модельный провайдер не публикуются Compose. Внутренние targets: `identity_service:50052`, `conversation_service:50051`, `legal_qa_service:50053`. Для локального провайдера на хосте Linux доступен `host.docker.internal`. Для межсерверных соединений требуется TLS; текущая внутренняя сеть gRPC предназначена для одного Docker-хоста. Gateway получает только открытый ключ, Identity — только закрытый. Не отправляйте `.env`, `.local` и архив в Git.

`/health/live` показывает работу процесса Gateway, `/health/ready` проверяет gRPC health трёх сервисов, не вызывая модель. У Legal QA снимок валидируется при запуске; текущий health самого сервиса не перепроверяет повреждение каталога после старта. Для диагностики: `docker compose logs --tail=100 gateway identity_service conversation_service legal_qa_service` и `docker compose ps -a`. Спецификация публичных маршрутов доступна на `http://localhost:8000/docs`.

## Проверки

```sh
buf lint && buf build
uv sync --locked --project services/identity_service
uv run --locked --project services/identity_service pytest services/identity_service/tests
uv sync --locked --project services/gateway
uv run --locked --project services/gateway pytest services/gateway/tests
(cd services/legal_qa_service && uv sync --locked && uv run --locked python -m unittest discover -s tests -v)
(cd services/conversation_service && go test ./...)
```

Для PostgreSQL-интеграционных тестов нужны **отдельные тестовые** базы; переменные и требования указаны в README соответствующих сервисов. CI также создаёт вымышленный корпус и использует [тестовый провайдер](infra/ci/model_proxy.py): он проверяет интеграцию, а не качество ответа модели. Оставшиеся доработки, приёмка на предоставленном корпусе и подготовка к реальной модели описаны в [единственном актуальном задании F-01](docs/tasks/final.md).

## Финальная проверка Legal QA

Команды корпуса, синтетических регрессий, корневого автономного ZIP и будущего прогона модели приведены в [README Legal QA](services/legal_qa_service/README.md). Фактические результаты и ограничения — в [отчёте F-01](docs/validation/final-backend.md). Полные ответы и предоставленные материалы сохраняются вне Git.
