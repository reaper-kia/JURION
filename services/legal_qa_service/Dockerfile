FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/
WORKDIR /app/services/legal_qa_service
COPY packages/platform_contracts /app/packages/platform_contracts
COPY services/legal_qa_service /app/services/legal_qa_service
RUN uv sync --locked --no-dev
ENV PATH="/app/services/legal_qa_service/.venv/bin:$PATH"
EXPOSE 50053
CMD ["python", "-m", "legal_qa.transport.grpc_server"]
