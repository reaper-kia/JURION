# JURION Identity

Identity управляет пользователями и refresh-сессиями JURION. Он работает с отдельной PostgreSQL и отдельной RSA-парой JURION. Не применяйте миграции к базе Casino Platform и не используйте её ключи.

## Настройки для общего Compose

| Настройка | Identity | Gateway |
| --- | --- | --- |
| База | `DATABASE_URL=postgresql+asyncpg://jurion_identity:<пароль>@identity_db:5432/jurion_identity` | Не подключается к БД Identity |
| Адрес gRPC | `GRPC_ADDRESS=[::]:50052` | `IDENTITY_GRPC_TARGET=identity_service:50052` |
| Служебный токен | `GATEWAY_IDENTITY_RPC_TOKEN` | То же значение `GATEWAY_IDENTITY_RPC_TOKEN` |
| Ключ | `ACCESS_TOKEN_PRIVATE_KEY_PATH=/run/jurion/private.pem` | Только соответствующий публичный PEM через `JWT_PUBLIC_KEY` |
| Издатель и аудитория | `ACCESS_TOKEN_ISSUER=jurion-identity`, `ACCESS_TOKEN_AUDIENCE=jurion-api` | `JWT_ISSUER=jurion-identity`, `JWT_AUDIENCE=jurion-api` |

Указанные issuer и audience — значения по умолчанию Identity и заданные значения в Compose. `ACCESS_TOKEN_TTL_SECONDS` по умолчанию равен 600, `REFRESH_TOKEN_TTL_SECONDS` — 2592000. Пароль в URL должен быть URL-safe либо корректно закодирован. Все служебные RPC Identity требуют metadata `x-jurion-service-token`; actor и права передаются только доверенным Gateway после проверки JWT. Внутренний gRPC не использует TLS, поэтому для соединений между хостами нужен защищённый транспорт.

В Compose Identity и PostgreSQL доступны только внутренней сети: наружу публикуется HTTP Gateway. PostgreSQL health предшествует `identity_migrate`; миграции завершаются до старта Identity. Identity при запуске проверяет RSA-ключ и соединение с БД. Gateway запускается после старта Identity и проверяет его по внутреннему gRPC Health в `/health/ready` вместе с Conversation и Legal QA. Повторный Compose `up` заново выполняет `alembic upgrade head`, но уже применённые ревизии не запускаются повторно и данные сохраняются. Состояние gRPC health показывает успешный запуск, но не проверяет подключение к БД непрерывно после старта.

## Сборка и запуск

Для полного запуска создайте **новую** тестовую RSA-пару и задайте архив корпуса и остальные секреты по [корневой инструкции](../../README.md). Identity получает только закрытый ключ, Gateway — только открытый. Используйте собственный `IDENTITY_DB_PASSWORD` и уникальный `GATEWAY_IDENTITY_RPC_TOKEN`; не сохраняйте секреты в Git.

Из корня репозитория:

```sh
docker compose config --quiet
docker compose build identity_service identity_migrate
docker compose up --build -d
docker compose ps -a
curl -fsS http://localhost:8000/health/ready
```

Миграция уже выполняется автоматически в `identity_migrate` до запуска Identity. При необходимости её можно отдельно повторить на той же настроенной БД:

```sh
docker compose run --rm identity_migrate alembic upgrade head
```

Сборка отдельного образа и команда миграции внутри него:

```sh
docker build -f services/identity_service/Dockerfile -t jurion-identity:local .
docker run --rm --network <сеть-с-доступом-к-бд> \
  -e DATABASE_URL='postgresql+asyncpg://<user>:<password>@<host>:5432/<identity_db>' \
  jurion-identity:local alembic upgrade head
```

`docker compose down` сохраняет тома. Перед удалением томов убедитесь, что данные больше не нужны.

Для самостоятельного Python-запуска из каталога сервиса нужны Python 3.13 и `uv`:

```sh
uv sync --locked
# Задайте DATABASE_URL, ACCESS_TOKEN_PRIVATE_KEY_PATH и GATEWAY_IDENTITY_RPC_TOKEN.
uv run --locked alembic upgrade head
uv run --locked identity-service
uv run --locked identity-create-admin --email admin@example.com --nickname admin
```

CLI запрашивает пароль без отображения и отказывает, если email уже занят. Для Gateway требуется соответствующий публичный ключ и согласованные настройки из таблицы выше.

## Проверки

```sh
# Из каталога services/identity_service.
# Тесты пересоздают таблицы: укажите только отдельную временную тестовую БД,
# имя которой содержит test; существующие данные в ней будут удалены.
TEST_DATABASE_URL='postgresql+asyncpg://<user>:<password>@<host>:5432/<identity_test>' \
  uv run --locked pytest tests

# Из корня; проверяет работающий Gateway и создаёт тестового пользователя.
JURION_TEST_URL=http://127.0.0.1:8000 PUBLIC_ORIGIN=http://localhost:8000 \
  python services/identity_service/tests/acceptance/gateway_auth.py
```

Приёмочный скрипт проверяет `register → me → refresh → logout → refresh`, повтор старого refresh, роль `lawyer` и неизменность `user_id` после входа. Он выводит email и ID тестового пользователя, но не токены. Для проверки сохранности после повторного `up` передайте выведенные значения как `--email` и `--expect-user-id`. Используйте только тестовый стек с соответствующим `PUBLIC_ORIGIN` и HTTP-cookie (`REFRESH_COOKIE_SECURE=false`).

Identity предоставляет Register, Login, RefreshToken, Logout, GetMe, GetUser, ListUsers и BlockUser. Health: `grpc.health.v1.Health/Check`, имя сервиса `identity.v1.IdentityService` либо пустая строка; его вызывают только во внутренней сети. Logout отзывает refresh-сессии; уже выданный access JWT остаётся действительным до `exp` при локальной проверке Gateway.
