# Conversation Service

Go 1.23+, PostgreSQL, gRPC. Сервис владеет отдельной базой. Запускает worker в том же процессе; повтор после сбоя зарезервированной задачи доступен после истечения дедлайна.

## Генерация контрактов

В корне репозитория: `services/conversation_service/generate.sh`. Нужны `protoc`, стандартные protobuf include-файлы и доступ к Go proxy. Скрипт устанавливает `protoc-gen-go` 1.36.5 и `protoc-gen-go-grpc` 1.5.1 во временный каталог и генерирует общий Go-модуль в `packages/platform_contracts/go` с `paths=source_relative`.

## Запуск

Создайте отдельную базу и примените `psql "$CONVERSATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_init.sql` из папки сервиса. Затем `go run ./cmd/conversation_service`. Миграция применяется один раз, не автоматически.

Обязательные переменные: `CONVERSATION_DATABASE_URL`, `GATEWAY_CONVERSATION_RPC_TOKEN`, `CONVERSATION_LEGAL_QA_RPC_TOKEN`. Дополнительные: `CONVERSATION_GRPC_ADDRESS` (по умолчанию `:50051`), `LEGAL_QA_GRPC_TARGET` (`localhost:50053`), `CONVERSATION_WORKERS` (2), `ANSWER_TIMEOUT_SECONDS` (90), `SHORT_RPC_TIMEOUT_SECONDS` (3). Внутреннее соединение предназначено для закрытой сети и не использует TLS.

Доступны шесть методов `conversation.v1.ConversationService` из контракта и `grpc.health.v1.Health/Check`, который проверяет собственную БД. На входе, кроме health, требуется metadata `x-jurion-service-token` с токеном Gateway. Сборка образа из корня: `docker build -f services/conversation_service/Dockerfile -t jurion-conversation:local .`.

## Проверки

`go test ./...` запускает модульные тесты. Интеграционный тест очищает все таблицы Conversation, поэтому предназначен только для отдельной тестовой БД с применённой миграцией: `CONVERSATION_TEST_DATABASE_URL=... go test ./... -count=1`. Для проверки совместимости контрактов: `buf lint` и `buf build` из корня. Сквозная интеграция требует запущенных Gateway и Legal QA.

## Диагностика

`GET /metrics` на `CONVERSATION_METRICS_ADDRESS` (по умолчанию `127.0.0.1:9091`) отдаёт агрегаты в текстовом формате Prometheus: ожидающие и зарезервированные задачи, количество и суммарное время ожидания, завершения, ошибки по стабильному коду, количество и суммарную длительность RPC Legal QA. Состояния и время ожидания рассчитываются по БД; счётчики RPC относятся к текущему процессу. Порт предназначен для внутренней сети. Текст сообщений, токены и ID пользователей не используются как метки. Журнал связывает `request_id` с `run_id`.

## Приёмка с настоящим Legal QA

Нужны импортированный каталог Legal QA, установленный Python-пакет Legal QA с зависимостями и отдельная мигрированная тестовая база. Интеграционный тест **очищает все таблицы** в этой базе. Он подключается к настоящему gRPC-сервису Legal QA и проверяет создание чата, идемпотентность, изоляцию, ответ, цитату, сбой модели и retry. Локальный провайдер из `tests/model_proxy.py` возвращает первый найденный фрагмент; он проверяет интеграцию, но не качество ответа.

Пример из корня репозитория (каждую долгоживущую команду запустить в отдельном терминале):

```sh
export CONVERSATION_E2E_MODEL_FAILURE_FLAG=/tmp/jurion-model-failure-flag
python services/conversation_service/tests/model_proxy.py
```

```sh
PYTHONPATH=services/legal_qa_service:packages/platform_contracts/src \
  LEGAL_QA_CATALOG=/path/to/test-catalog \
  GATEWAY_LEGAL_QA_RPC_TOKEN=qa-gateway-secret \
  CONVERSATION_LEGAL_QA_RPC_TOKEN=conversation-secret \
  LEGAL_QA_GRPC_ADDRESS=127.0.0.1:55440 \
  LLM_BASE_URL=http://127.0.0.1:55441 LLM_API_KEY=test LLM_MODEL=test \
  python -m legal_qa.transport.grpc_server
```

```sh
cd services/conversation_service
CONVERSATION_E2E_DATABASE_URL='postgres://.../dedicated_test_db' \
  CONVERSATION_E2E_LEGAL_TARGET=127.0.0.1:55440 \
  CONVERSATION_E2E_MODEL_FAILURE_FLAG=/tmp/jurion-model-failure-flag \
  go test ./internal/e2e -count=1 -v
```

Тест использует тестовые служебные токены из примера. Проверка через публичный Gateway и прокси организаторов выполняется отдельно.
