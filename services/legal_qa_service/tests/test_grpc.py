from pathlib import Path
import tempfile
import unittest
import uuid

try:
    import grpc
    from common.v1 import common_pb2
    from legal_qa.v1 import legal_qa_service_pb2 as pb
    from legal_qa.corpus import publish, load_snapshot
    from legal_qa.transport.grpc_server import Servicer
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

CORPUS = Path('/home/reaper/knowledge-base.zip')


class Abort(Exception):
    def __init__(self, status):
        self.status = status


class Context:
    def __init__(self, token=None):
        self.token = token
        self.trailing = ()
    def invocation_metadata(self):
        return [('x-jurion-service-token', self.token)] if self.token else []
    def set_trailing_metadata(self, metadata):
        self.trailing = metadata
    def abort(self, status, message):
        raise Abort(status)
    def time_remaining(self):
        return 5


@unittest.skipUnless(AVAILABLE and CORPUS.exists(), 'gRPC dependencies or corpus missing')
class GrpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.sid = publish(CORPUS, Path(cls.temp.name))
        cls.service = Servicer(Path(cls.temp.name), 'gateway-secret', 'conversation-secret')
        cls.actor = common_pb2.ActorContext(request_id='request', user_id=str(uuid.uuid4()), permissions=['sources:read'])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_open_chunk_and_original(self):
        manifest, originals = load_snapshot(Path(self.temp.name), self.sid)
        chunk = next(c for c in manifest['chunks'] if c['provision_label'] == '3.1' and c['line_start'] == 14)
        ctx = Context('gateway-secret')
        response = self.service.GetSourceChunk(pb.GetSourceChunkRequest(actor=self.actor, snapshot_id=self.sid, chunk_id=chunk['id']), ctx)
        self.assertEqual(response.text, chunk['text'])
        self.assertEqual(response.line_start, 14)
        file = self.service.GetSourceFile(pb.GetSourceFileRequest(actor=self.actor, snapshot_id=self.sid, file_id=response.file.id), ctx)
        self.assertEqual(file.content, originals[response.file.id])
        with self.assertRaises(Abort) as error:
            self.service.GetSourceFile(pb.GetSourceFileRequest(actor=self.actor, snapshot_id=self.sid, file_id='../bad'), ctx)
        self.assertEqual(error.exception.status, grpc.StatusCode.NOT_FOUND)

    def test_authentication_and_method_boundary(self):
        request = pb.GetSourceChunkRequest(actor=self.actor, snapshot_id=self.sid, chunk_id='missing')
        with self.assertRaises(Abort) as error:
            self.service.GetSourceChunk(request, Context())
        self.assertEqual(error.exception.status, grpc.StatusCode.UNAUTHENTICATED)
        ctx = Context('conversation-secret')
        with self.assertRaises(Abort) as error:
            self.service.GetSourceChunk(request, ctx)
        self.assertEqual(error.exception.status, grpc.StatusCode.PERMISSION_DENIED)
        self.assertEqual(dict(ctx.trailing)['jurion-error-code'], 'SERVICE_FORBIDDEN')
