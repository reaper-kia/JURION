import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    public_origin: str = os.getenv("PUBLIC_ORIGIN", "http://localhost:8000").rstrip("/")
    cookie_secure: bool = os.getenv("REFRESH_COOKIE_SECURE", "true").lower() == "true"
    jwt_public_key: str = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "jurion-identity")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "jurion-api")
    identity_target: str = os.getenv("IDENTITY_GRPC_TARGET", "identity:50052")
    conversation_target: str = os.getenv(
        "CONVERSATION_GRPC_TARGET", "conversation:50051"
    )
    legal_qa_target: str = os.getenv("LEGAL_QA_GRPC_TARGET", "legal-qa:50051")
    identity_token: str = os.getenv("GATEWAY_IDENTITY_RPC_TOKEN", "")
    conversation_token: str = os.getenv("GATEWAY_CONVERSATION_RPC_TOKEN", "")
    legal_qa_token: str = os.getenv("GATEWAY_LEGAL_QA_RPC_TOKEN", "")
    rpc_timeout: float = float(os.getenv("GRPC_TIMEOUT_SECONDS", "3"))
    max_body: int = int(os.getenv("MAX_BODY_BYTES", "65536"))
    auth_rate_limit: int = int(os.getenv("AUTH_RATE_LIMIT", "10"))
