FROM python:3.13-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

WORKDIR /app/services/identity_service

COPY packages/platform_contracts /app/packages/platform_contracts
COPY services/identity_service/pyproject.toml services/identity_service/uv.lock services/identity_service/README.md ./

RUN uv sync --locked --no-dev --no-install-project

COPY services/identity_service/src ./src
COPY services/identity_service/migrations ./migrations
COPY services/identity_service/alembic.ini ./alembic.ini

RUN uv sync --locked --no-dev

ENV PATH="/app/services/identity_service/.venv/bin:$PATH"

EXPOSE 50052

CMD ["identity-service"]