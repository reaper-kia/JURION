"""Internal gRPC transport for immutable catalog and answer queries."""
from concurrent import futures
from datetime import date, datetime, timezone
import hmac
import os
from pathlib import Path
import re
import time
import uuid

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from legal_qa.v1 import legal_qa_service_pb2 as pb
from legal_qa.v1 import legal_qa_service_pb2_grpc as rpc

from legal_qa.application import Dispatcher, ReadSnapshot, AnswerQuery

def load_snapshot(root, snapshot_id=None):
    return Dispatcher().dispatch(ReadSnapshot(root, snapshot_id))
from legal_qa.answer import answer as answer_query, ModelUnavailable, ProxyGenerator

KB_ID = 'meridian'


class Servicer(rpc.LegalQaServiceServicer):
    def __init__(self, root: Path, gateway_token: str, conversation_token: str, answer=None):
        if not gateway_token or not conversation_token or hmac.compare_digest(gateway_token, conversation_token):
            raise ValueError('Distinct service tokens are required')
        self.root = root
        self.gateway_token = gateway_token
        self.conversation_token = conversation_token
        self.answer = answer

    @staticmethod
    def fail(context, status, code, message):
        context.set_trailing_metadata((('jurion-error-code', code),))
        context.abort(status, message)

    def authenticate(self, context, allowed):
        values = [v for k, v in context.invocation_metadata() if k == 'x-jurion-service-token']
        if len(values) != 1:
            self.fail(context, grpc.StatusCode.UNAUTHENTICATED, 'SERVICE_UNAUTHENTICATED', 'Service authentication required')
        token = values[0]
        kind = ('gateway' if hmac.compare_digest(token, self.gateway_token) else
                'conversation' if hmac.compare_digest(token, self.conversation_token) else None)
        if kind is None:
            self.fail(context, grpc.StatusCode.UNAUTHENTICATED, 'SERVICE_UNAUTHENTICATED', 'Service authentication required')
        if kind not in allowed:
            self.fail(context, grpc.StatusCode.PERMISSION_DENIED, 'SERVICE_FORBIDDEN', 'Method forbidden')

    def actor(self, request, context):
        if not request.HasField('actor') or not request.actor.request_id.strip():
            self.fail(context, grpc.StatusCode.INVALID_ARGUMENT, 'VALIDATION_ERROR', 'Actor required')
        try:
            uuid.UUID(request.actor.user_id)
        except ValueError:
            self.fail(context, grpc.StatusCode.INVALID_ARGUMENT, 'VALIDATION_ERROR', 'Invalid actor')
        if 'sources:read' not in request.actor.permissions:
            self.fail(context, grpc.StatusCode.PERMISSION_DENIED, 'FORBIDDEN', 'Permission required')

    def snapshot(self, context, snapshot_id=None):
        try:
            return load_snapshot(self.root, snapshot_id)
        except (ValueError, OSError, KeyError):
            if snapshot_id is not None:
                self.fail(context, grpc.StatusCode.NOT_FOUND, 'NOT_FOUND', 'Source not found')
            self.fail(context, grpc.StatusCode.UNAVAILABLE, 'SERVICE_UNAVAILABLE', 'Catalog unavailable')

    def ListKnowledgeBases(self, request, context):
        self.authenticate(context, ('gateway', 'conversation'))
        self.actor(request, context)
        self.snapshot(context)
        return pb.ListKnowledgeBasesResponse(items=[pb.KnowledgeBase(id=KB_ID, title='Корпус ООО «Меридиан»')])

    def GetSourceChunk(self, request, context):
        self.authenticate(context, ('gateway',))
        self.actor(request, context)
        manifest, _ = self.snapshot(context, request.snapshot_id)
        chunk = next((c for c in manifest['chunks'] if c['id'] == request.chunk_id), None)
        if chunk is None:
            self.fail(context, grpc.StatusCode.NOT_FOUND, 'NOT_FOUND', 'Source not found')
        file = next(f for f in manifest['files'] if f['id'] == chunk['file_id'])
        result = pb.GetSourceChunkResponse(chunk_id=chunk['id'], snapshot_id=request.snapshot_id,
            document_title=file['title'], text=chunk['text'], line_start=chunk['line_start'], line_end=chunk['line_end'],
            file=pb.SourceFileRef(id=file['id'], name=file['name'], media_type=file['media_type']))
        if file['version_label']:
            result.version_label = file['version_label']
        if chunk['provision_label']:
            result.provision_label = chunk['provision_label']
        return result

    def GetSourceFile(self, request, context):
        self.authenticate(context, ('gateway',))
        self.actor(request, context)
        manifest, originals = self.snapshot(context, request.snapshot_id)
        file = next((f for f in manifest['files'] if f['id'] == request.file_id), None)
        if file is None:
            self.fail(context, grpc.StatusCode.NOT_FOUND, 'NOT_FOUND', 'Source not found')
        return pb.GetSourceFileResponse(file=pb.SourceFileRef(id=file['id'], name=file['name'], media_type=file['media_type']), content=originals[file['id']])

    def Answer(self, request, context):
        self.authenticate(context, ('conversation',))
        if not request.request_id.strip() or not request.run_id.strip() or request.knowledge_base_id != KB_ID:
            self.fail(context, grpc.StatusCode.INVALID_ARGUMENT, 'VALIDATION_ERROR', 'Invalid answer request')
        if (not request.messages or len(request.messages) > 100 or
            request.messages[-1].role != pb.MESSAGE_ROLE_USER or
            any(m.role not in (pb.MESSAGE_ROLE_USER, pb.MESSAGE_ROLE_ASSISTANT) or not m.text.strip() or len(m.text) > 20000 for m in request.messages)):
            self.fail(context, grpc.StatusCode.INVALID_ARGUMENT, 'VALIDATION_ERROR', 'Invalid history')
        try:
            if request.HasField('as_of_date'):
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', request.as_of_date):
                    raise ValueError('invalid date')
                date.fromisoformat(request.as_of_date)
            if not request.HasField('deadline_at'):
                raise ValueError('deadline required')
            remaining = (request.deadline_at.ToDatetime(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, OverflowError):
            self.fail(context, grpc.StatusCode.INVALID_ARGUMENT, 'VALIDATION_ERROR', 'Invalid date or deadline')
        rpc_remaining = context.time_remaining()
        remaining = min(remaining, rpc_remaining) if rpc_remaining is not None else remaining
        if remaining <= 0:
            self.fail(context, grpc.StatusCode.DEADLINE_EXCEEDED, 'ANSWER_TIMEOUT', 'Deadline exceeded')
        if self.answer is not None:
            self.snapshot(context)
            return self.answer(request, remaining)
        expires = time.monotonic() + remaining
        try:
            sid = (self.root / 'active').read_text(encoding='ascii').strip()
            manifest, _ = load_snapshot(self.root, sid)
            messages = [('user' if m.role == pb.MESSAGE_ROLE_USER else 'assistant', m.text) for m in request.messages]
            as_of = date.fromisoformat(request.as_of_date) if request.HasField('as_of_date') else None
            result = Dispatcher().dispatch(AnswerQuery(manifest, messages, ProxyGenerator.from_env(), as_of, expires))
            response = pb.AnswerResponse(snapshot_id=sid, outcome=pb.Outcome.Value('OUTCOME_' + result.outcome.upper()),
                text=result.text, missing_information=result.missing_information)
            for claim in result.claims:
                response.claims.add(text=claim['text'], citations=[pb.Citation(**c) for c in claim['citations']])
            if result.clarification_question:
                response.clarification_question = result.clarification_question
            if result.provider:
                response.provider, response.model = result.provider, result.model
            return response
        except TimeoutError:
            self.fail(context, grpc.StatusCode.DEADLINE_EXCEEDED, 'ANSWER_TIMEOUT', 'Deadline exceeded')
        except ModelUnavailable:
            self.fail(context, grpc.StatusCode.UNAVAILABLE, 'MODEL_UNAVAILABLE', 'Model unavailable')
        except (OSError, ValueError, KeyError):
            self.fail(context, grpc.StatusCode.UNAVAILABLE, 'SERVICE_UNAVAILABLE', 'Catalog unavailable')


def serve():
    root = Path(os.environ['LEGAL_QA_CATALOG'])
    load_snapshot(root)
    service = Servicer(root, os.environ['GATEWAY_LEGAL_QA_RPC_TOKEN'], os.environ['CONVERSATION_LEGAL_QA_RPC_TOKEN'])
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    rpc.add_LegalQaServiceServicer_to_server(service, server)
    class CatalogHealth(health.HealthServicer):
        def Check(self, request, context):
            try:
                load_snapshot(root)
                status = health_pb2.HealthCheckResponse.SERVING
            except (OSError, ValueError, KeyError):
                status = health_pb2.HealthCheckResponse.NOT_SERVING
            return health_pb2.HealthCheckResponse(status=status)
    health_service = CatalogHealth()
    health_pb2_grpc.add_HealthServicer_to_server(health_service, server)
    health_service.set('', health_pb2.HealthCheckResponse.SERVING)
    health_service.set('legal_qa.v1.LegalQaService', health_pb2.HealthCheckResponse.SERVING)
    address = os.getenv('LEGAL_QA_GRPC_ADDRESS', '[::]:50051')
    if not server.add_insecure_port(address):
        raise RuntimeError('Cannot bind gRPC address')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
