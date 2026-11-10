# Проверка интеграции Gateway · 11 ноября 2026

Проверки выполнены в отдельных Docker Compose проектах `jurion_g04_test` и `jurion_ci_verify`, с новыми ключами и тестовыми секретами. Настоящее ядро Legal QA использовало предоставленный архив и отдельно вымышленный архив для CI; модель заменена управляемым локальным провайдером из `infra/ci/model_proxy.py`. Проверка не оценивает качество модели.

| Проверка | Результат |
| --- | --- |
| `docker compose ... config --quiet` | Успех |
| `docker compose ... up --build -d --wait` на чистых тестовых томах | Собраны четыре приложения, обе миграции и импорт завершились, Gateway ready |
| `docker compose ... ps -a` | На хост опубликован только Gateway (`127.0.0.1:18080`); БД и gRPC без опубликованных портов |
| Повторный `up`, обычный перезапуск и чтение истории | Успех; миграция Conversation не применяется повторно |
| Публичный сценарий из `infra/ci/acceptance.py` | Регистрация, me, refresh, база, чат, `202`, polling, цитата и TXT, идемпотентность, изоляция второго пользователя, logout и повторный вход — успех |
| Управляемый сбой модели и retry | `MODEL_UNAVAILABLE`, новая попытка с прежним ID вопроса, завершение без дубликата |
| Публикация другого снимка и повторный `up` | Новый снимок остаётся активным; фрагмент и оригинал по старому ID доступны и совпадают |
| Остановленный Legal QA | `/health/ready` возвращает 503; публичное чтение базы возвращает `SERVICE_UNAVAILABLE` |
| `buf lint && buf build` | Успех |
| Python-генерация через `uv run --locked --project services/identity_service python scripts/generate_proto.py` | Совпадает с исходными сгенерированными файлами |
| Go-генерация через `services/conversation_service/generate.sh` | Совпадает с исходными сгенерированными файлами |
| `uv run --locked --project services/gateway pytest services/gateway/tests` | 10 тестов прошли |
| `pytest services/identity_service/tests` с отдельной PostgreSQL `jurion_identity_test` | 57 тестов прошли |
| `(cd services/conversation_service && go test ./... -count=1)` с отдельной мигрированной PostgreSQL `jurion_conversation_test` | Успех; отдельный Go e2e с внешними настройками пропущен, публичная интеграция проверена Compose-сценарием |
| `(cd services/legal_qa_service && uv run --locked python -m unittest discover -s tests)` | 15 тестов прошли в локальном окружении с предоставленными файлами |
| Ruff Gateway и проверка форматирования | Успех |

Для воспроизведения используйте [README](../README.md), а для тестового модельного провайдера — `COMPOSE_FILE=compose.yaml:infra/ci/compose.yaml` и `LLM_BASE_URL=http://model_proxy:55441`. CI сам создаёт ключи и вымышленный корпус, затем выполняет `infra/ci/acceptance.py`. GitHub Actions после изменения workflow в этом окружении не запускался; его итоговый статус необходимо проверить после публикации изменений. Актуальные ограничения Legal QA и его готовности к проверке качества приведены в [README сервиса](../services/legal_qa_service/README.md).
