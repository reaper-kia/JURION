import pytest
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc

from identity_service.transport.grpc.server import create_server


@pytest.mark.asyncio
async def test_health_check_reports_serving() -> None:
    server, port = await create_server(None, "127.0.0.1:0", "test-service-token")
    await server.start()

    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = health_pb2_grpc.HealthStub(channel)
            response = await stub.Check(
                health_pb2.HealthCheckRequest(service=""),
                timeout=3,
            )

        assert response.status == health_pb2.HealthCheckResponse.SERVING
    finally:
        await server.stop(grace=0)
