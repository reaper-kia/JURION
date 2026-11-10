# Gateway JURION

FastAPI-шлюз для браузера. Контракт: [docs/api.md](../../docs/api.md); внутренние вызовы: [contract](../../contract). Gateway не хранит доменные данные. Внутренние gRPC-порты должны быть доступны только в закрытой сети; каналы без TLS предназначены только для такой сети.

## Запуск

Python 3.13 и `uv`:

```sh
uv sync --project services/gateway
export PUBLIC_ORIGIN=http://localhost:8000 REFRESH_COOKIE_SECURE=false
export JWT_PUBLIC_KEY="$(cat /path/to/jurion-public.pem)"
export GATEWAY_IDENTITY_RPC_TOKEN=local-identity-secret
export GATEWAY_CONVERSATION_RPC_TOKEN=local-conversation-secret
export GATEWAY_LEGAL_QA_RPC_TOKEN=local-legal-qa-secret
uv run --project services/gateway uvicorn gateway.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Публичный ключ соответствует закрытому ключу Identity, не Casino Platform. Секреты выше — только пример для локальной изолированной среды; в реальном окружении используйте разные секреты из менеджера секретов. Настройте адреса для трёх сервисов и запустите их отдельно. Не включайте access-логи прокси с телами запросов или секретными заголовками.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `PUBLIC_ORIGIN` | `http://localhost:8000` | Единственный разрешённый Origin/Referer для POST авторизации |
| `REFRESH_COOKIE_SECURE` | `true` | `false` только для явно настроенного локального HTTP |
| `JWT_PUBLIC_KEY` | пусто | Публичный RSA PEM JURION (допускаются `\\n` вместо переводов строк) |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `jurion-identity` / `jurion-api` | Должны совпадать с Identity |
| `IDENTITY_GRPC_TARGET` | `identity:50052` | Адрес Identity |
| `CONVERSATION_GRPC_TARGET` / `LEGAL_QA_GRPC_TARGET` | `conversation:50051` / `legal-qa:50051` | Адреса gRPC |
| `GATEWAY_IDENTITY_RPC_TOKEN`, `GATEWAY_CONVERSATION_RPC_TOKEN`, `GATEWAY_LEGAL_QA_RPC_TOKEN` | пусто | Отдельные секреты связей; необходимо задать |
| `GRPC_TIMEOUT_SECONDS` | `3` | Таймаут каждого вызова, включая health |
| `MAX_BODY_BYTES` | `65536` | Максимальный размер входного тела |
| `AUTH_RATE_LIMIT` | `10` | Число попыток login/register с одного адреса за скользящие 60 секунд на одну реплику |

Лимитер хранится в памяти процесса и не разделяется между репликами; при горизонтальном масштабировании нужен общий периметр. За обратным прокси адрес клиента определяется сетевым соединением; настройте ограничение на периметре, если все клиенты видны под одним адресом.

Маршруты API перечислены в `docs/api.md`. Диагностика: `GET /health/live`, `GET /health/ready`, документация `/docs`. Readiness запрашивает gRPC Health у всех трёх сервисов и не вызывает модель. Открывать наружу следует только порт Gateway; Identity, Conversation, Legal QA и базы данных — только внутри сети.

## Проверки

```sh
uv run --project services/gateway pytest services/gateway/tests
uv run --project services/gateway ruff check services/gateway/src services/gateway/tests
```

Для реального сквозного сценария нужны запущенные Identity, Conversation и Legal QA, их секреты и готовые базы/корпус. Корневой Compose и CI описаны в [общем README](../../README.md). Публичное администрирование (G-05) ожидает согласования отдельного HTTP-контракта.
