"""Test the public stack with the real Legal QA core and a controlled model provider."""
import http.cookiejar
import json
import os
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
import urllib.error
import urllib.request
import uuid

BASE = os.getenv('JURION_TEST_URL', 'http://127.0.0.1:8000')
ORIGIN = os.getenv('PUBLIC_ORIGIN', 'http://localhost:8000')


def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(session, method, path, *, data=None, token=None, key=None, expected=200):
    headers = {'Origin': ORIGIN}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if key:
        headers['Idempotency-Key'] = key
    payload = None if data is None else json.dumps(data).encode()
    if payload:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE + path, method=method, headers=headers, data=payload)
    try:
        response = session.open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        response = exc
    raw = response.read()
    assert response.status == expected, (path, response.status, raw[:1000])
    return response, json.loads(raw) if raw and 'application/json' in response.headers.get('Content-Type', '') else raw


def poll(session, token, run_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        _, run = call(session, 'GET', '/api/v1/runs/' + run_id, token=token)
        if run['state'] != 'running':
            return run
        time.sleep(.2)
    raise AssertionError('Timed out waiting for run')


def model_failure(enabled):
    operation = "open('/tmp/model-failure','w').close()" if enabled else "__import__('os').unlink('/tmp/model-failure')"
    subprocess.run(['docker', 'compose', 'exec', '-T', 'model_proxy', 'python', '-c', operation], check=True)


def main():
    session, other = client(), client()
    nonce = uuid.uuid4().hex
    body = {'email': f'lawyer-{nonce}@example.test', 'nickname': 'Test Lawyer', 'password': 'TestPassword123!'}
    _, auth = call(session, 'POST', '/api/v1/auth/register', data=body, expected=201)
    token = auth['access_token']
    call(session, 'GET', '/api/v1/auth/me', token=token)
    _, refreshed = call(session, 'POST', '/api/v1/auth/refresh')
    token = refreshed['access_token']
    _, bases = call(session, 'GET', '/api/v1/knowledge-bases', token=token)
    _, conversation = call(session, 'POST', '/api/v1/conversations', token=token, data={'knowledge_base_id': bases['items'][0]['id']}, expected=201)
    conv = conversation['id']
    message_url = f'/api/v1/conversations/{conv}/messages'
    key = str(uuid.uuid4())
    question = {'text': os.getenv('JURION_TEST_QUESTION', 'Какая оплата аренды?')}
    _, run = call(session, 'POST', message_url, token=token, key=key, data=question, expected=202)
    run_id = run['run_id']
    # The first run can finish before the repeat, so both success statuses are valid.
    try:
        _, repeated = call(session, 'POST', message_url, token=token, key=key, data=question, expected=202)
    except AssertionError:
        _, repeated = call(session, 'POST', message_url, token=token, key=key, data=question, expected=200)
    assert repeated['run_id'] == run_id
    result = poll(session, token, run_id)
    assert result['state'] == 'completed', result
    answer = result['assistant_message']['answer']
    cite = answer['claims'][0]['citations'][0]
    _, chunk = call(session, 'GET', f"/api/v1/sources/{answer['snapshot_id']}/chunks/{cite['chunk_id']}", token=token)
    response, original = call(session, 'GET', chunk['file']['url'], token=token)
    assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
    assert chunk['text'] in original.decode('utf-8')
    _, second = call(other, 'POST', '/api/v1/auth/register', data={**body, 'email': f'other-{nonce}@example.test'}, expected=201)
    other_token = second['access_token']
    call(other, 'GET', message_url, token=other_token, expected=404)
    call(other, 'GET', '/api/v1/runs/' + run_id, token=other_token, expected=404)
    _, clarify_chat = call(session, 'POST', '/api/v1/conversations', token=token, data={'knowledge_base_id': bases['items'][0]['id']}, expected=201)
    clarification_url = f"/api/v1/conversations/{clarify_chat['id']}/messages"
    _, pending = call(session, 'POST', clarification_url, token=token, key=str(uuid.uuid4()), data={'text':'Гарантия по договору с Альфой?'}, expected=202)
    clarified = poll(session, token, pending['run_id'])
    assert clarified['assistant_message']['answer']['outcome'] == 'needs_clarification', clarified
    _, pending = call(session, 'POST', clarification_url, token=token, key=str(uuid.uuid4()), data={'text':'Нет, это Альфа-Трейдинг. Какая гарантия?'}, expected=202)
    clarified = poll(session, token, pending['run_id'])
    assert clarified['assistant_message']['answer']['outcome'] == 'answered', clarified
    model_failure(True)
    try:
        _, started = call(session, 'POST', message_url, token=token, key=str(uuid.uuid4()), data=question, expected=202)
        failed = poll(session, token, started['run_id'])
        assert failed['state'] == 'failed' and failed['error']['code'] == 'MODEL_UNAVAILABLE', failed
    finally:
        model_failure(False)
    _, retry = call(session, 'POST', f"/api/v1/runs/{failed['run_id']}/retry", token=token, key=str(uuid.uuid4()), expected=202)
    assert retry['user_message']['id'] == failed['user_message']['id']
    assert poll(session, token, retry['run_id'])['state'] == 'completed'
    call(session, 'POST', '/api/v1/auth/logout', data={}, expected=204)
    _, login = call(session, 'POST', '/api/v1/auth/login', data={'email': body['email'], 'password': body['password']})
    _, history = call(session, 'GET', message_url, token=login['access_token'])
    assert len([m for m in history['items'] if m['role'] == 'user']) == 2
    # Publishing new content must keep the old snapshot and its source available.
    archive_path = os.getenv('LEGAL_QA_ARCHIVE')
    if archive_path:
        with tempfile.TemporaryDirectory(prefix='jurion-snapshot-') as directory:
            new_archive = Path(directory) / 'updated.zip'
            with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(new_archive, 'w') as target:
                for item in source.infolist():
                    target.writestr(item, source.read(item.filename))
                target.writestr(f'jurion-integration-{uuid.uuid4().hex}.txt', 'Статья 99. Тестовый документ для интеграции.\n')
            child_env = dict(os.environ, LEGAL_QA_ARCHIVE=str(new_archive))
            published = subprocess.run(['docker', 'compose', 'run', '--rm', '--no-deps', 'legal_qa_import', 'python', '-m', 'legal_qa', '/input/knowledge-base.zip', '--catalog', '/data/catalog'], env=child_env, check=True, capture_output=True, text=True).stdout.strip()
            assert published and published != answer['snapshot_id']
        subprocess.run(['docker', 'compose', 'up', '-d', '--no-build', '--wait', '--wait-timeout', '90'], check=True, stdout=subprocess.DEVNULL)
        active = subprocess.run(['docker', 'compose', 'exec', '-T', 'legal_qa_service', 'python', '-c', "print(open('/data/catalog/active').read().strip())"], check=True, capture_output=True, text=True).stdout.strip()
        assert active == published
        _, old_chunk = call(session, 'GET', f"/api/v1/sources/{answer['snapshot_id']}/chunks/{cite['chunk_id']}", token=login['access_token'])
        assert old_chunk['text'] == chunk['text']
        _, old_file = call(session, 'GET', old_chunk['file']['url'], token=login['access_token'])
        assert old_file == original
    subprocess.run(['docker', 'compose', 'restart', 'gateway', 'identity_service', 'conversation_service', 'legal_qa_service'], check=True, stdout=subprocess.DEVNULL)
    deadline = time.monotonic() + 30
    while True:
        try:
            call(session, 'GET', '/health/ready')
            break
        except (OSError, urllib.error.URLError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(.5)
    _, history = call(session, 'GET', message_url, token=login['access_token'])
    assert len([m for m in history['items'] if m['role'] == 'user']) == 2
    corrupt = "from pathlib import Path; p=Path('/data/catalog/active'); p.rename('/data/catalog/.acceptance-active'); p.write_text('corrupt')"
    restore = "from pathlib import Path; Path('/data/catalog/.acceptance-active').replace('/data/catalog/active')"
    subprocess.run(['docker','compose','exec','-T','legal_qa_service','python','-c',corrupt],check=True)
    try:
        call(session,'GET','/health/ready',expected=503)
    finally:
        subprocess.run(['docker','compose','exec','-T','legal_qa_service','python','-c',restore],check=True)
    subprocess.run(['docker', 'compose', 'stop', 'legal_qa_service'], check=True, stdout=subprocess.DEVNULL)
    try:
        call(session, 'GET', '/health/ready', expected=503)
        _, unavailable = call(session, 'GET', '/api/v1/knowledge-bases', token=login['access_token'], expected=503)
        assert unavailable['error']['code'] == 'SERVICE_UNAVAILABLE'
    finally:
        subprocess.run(['docker', 'compose', 'start', 'legal_qa_service'], check=True, stdout=subprocess.DEVNULL)
    print('Public flow, isolation, citation, model failure and retry passed')


if __name__ == '__main__':
    main()
