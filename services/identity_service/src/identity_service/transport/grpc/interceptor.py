import hmac

import grpc


class ServiceTokenInterceptor(grpc.aio.ServerInterceptor):
    def __init__(self, token: str):
        if not token:
            raise ValueError("GATEWAY_IDENTITY_RPC_TOKEN must not be empty")
        self._token = token

    async def intercept_service(self, continuation, details):
        if not details.method.startswith("/identity.v1.IdentityService/"):
            return await continuation(details)
        metadata = list(details.invocation_metadata or ())
        values = [v for k, v in metadata if k == "x-jurion-service-token"]
        if len(values) == 1 and hmac.compare_digest(values[0], self._token):
            return await continuation(details)

        async def deny(request, context):
            context.set_trailing_metadata((("jurion-error-code", "SERVICE_UNAUTHENTICATED"),))
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Service authentication required")

        return grpc.unary_unary_rpc_method_handler(deny)
