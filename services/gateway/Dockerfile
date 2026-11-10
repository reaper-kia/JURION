FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/
WORKDIR /app/services/gateway
COPY packages/platform_contracts /app/packages/platform_contracts
COPY services/gateway /app/services/gateway
RUN uv sync --locked --no-dev
ENV PATH="/app/services/gateway/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
