"""Controlled extractive drafts for integration; no demo answer lookup."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if Path('/tmp/model-failure').exists():
            self.send_response(503); self.end_headers(); return
        data = json.loads(request['messages'][-1]['content'])
        if 'draft' in data:
            result = {'supported': True, 'complete': True}
        else:
            evidence = data['evidence']
            item = next((e for e in evidence if 'аренд' in e['text'].lower() and 'рубл' in e['text'].lower()), evidence[0] if evidence else None)
            result = {'outcome':'answered' if item else 'insufficient_evidence',
                      'claims':[{'text':item['text'],'citations':[{'chunk_id':item['id'],'quote':item['text']}]}] if item else [],
                      'missing_information':[], 'clarification_question':None}
        body = json.dumps({'choices':[{'message':{'content':json.dumps(result)}}]}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',55441),Handler).serve_forever()
