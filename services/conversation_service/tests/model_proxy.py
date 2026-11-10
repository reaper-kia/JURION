"""Local test-only OpenAI-compatible provider; requires no network credentials."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if Path(os.environ['CONVERSATION_E2E_MODEL_FAILURE_FLAG']).exists():
            self.send_response(503)
            self.end_headers()
            return
        evidence = json.loads(payload['messages'][-1]['content'])['evidence']
        ids = [evidence[0]['id']] if evidence else []
        body = json.dumps({'choices': [{'message': {'content': json.dumps({'chunk_ids': ids})}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    HTTPServer(('127.0.0.1', int(os.getenv('CONVERSATION_E2E_MODEL_PORT', '55441'))), Handler).serve_forever()
