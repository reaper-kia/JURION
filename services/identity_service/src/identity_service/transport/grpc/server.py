import logging

from grpc import aio
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection
from identity.v1 import identity_service_pb2 as pb
from identity.v1 import identity_service_pb2_grpc as pb_grpc
from sqlalchemy import text

from identity_service.applications.mediator import Mediator
from identity_service.dependencies import build_container
from identity_service.infra.config import get_settings
from identity_service.transport.grpc.interceptor import ServiceTokenInterceptor
from identity_service.transport.grpc.servicer import IdentityServicer

logger = logging.getLogger(__name__)

SERVICE_NAMES = (
    pb.DESCRIPTOR.services_by_name["IdentityService"].full_name,
    health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
    reflection.SERVICE_NAME,
)


async def create_server(
    mediator: Mediator, address: str, service_token: str
) -> tuple[aio.Server, int]:
    server = aio.server(interceptors=[ServiceTokenInterceptor(service_token)])

    pb_grpc.add_IdentityServiceServicer_to_server(  # type: ignore[no-untyped-call]
        IdentityServicer(mediator), server
    )

    health_service = health.aio.HealthServicer()  # type: ignore[attr-defined]
    health_pb2_grpc.add_HealthServicer_to_server(health_service, server)
    await health_service.set("", health_pb2.HealthCheckResponse.SERVING)
    await health_service.set(SERVICE_NAMES[0], health_pb2.HealthCheckResponse.SERVING)

    reflection.enable_server_reflection(SERVICE_NAMES, server)

    port = server.add_insecure_port(address)

    if port == 0:
        raise RuntimeError(f"Cannot bind gRPC server to {address}")

    return server, port


async def serve() -> None:
    settings = get_settings()
    container = build_container(settings)

    async with container.engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    server, _ = await create_server(
        container.mediator, settings.grpc_address, settings.gateway_identity_rpc_token
    )
    await server.start()
    logger.info("Identity gRPC server listening on %s", settings.grpc_address)

    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=5)
        await container.close()
