"""Exercise Identity through a running Gateway; never print tokens or cookies."""

import argparse
import json
import os
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = os.environ.get("JURION_TEST_URL", "http://127.0.0.1:8000").rstrip("/")
ORIGIN = os.environ.get("PUBLIC_ORIGIN", "http://localhost:8000")
PASSWORD = "IdentityAcceptancePassword123!"


def call(method, path, *, body=None, cookie=None, token=None, expected=200):
    headers = {"Origin": ORIGIN}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if cookie is not None:
        headers["Cookie"] = f"jurion_refresh={cookie}"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        payload = response.read()
        if response.status != expected:
            raise AssertionError(f"{path}: expected HTTP {expected}, got {response.status}")
        parsed = json.loads(payload) if payload else None
        header = response.headers.get("Set-Cookie")
        cookies = SimpleCookie()
        if header:
            cookies.load(header)
        refresh = cookies["jurion_refresh"].value if "jurion_refresh" in cookies else None
        return parsed, refresh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=f"identity-{uuid4().hex}@example.test")
    parser.add_argument("--expect-user-id", help="Check a previously registered user after restart")
    args = parser.parse_args()
    prefix = "/api/v1/auth/"
    if args.expect_user_id:
        auth, _ = call("POST", prefix + "login", body={"email": args.email, "password": PASSWORD})
        assert auth["user"]["user_id"] == args.expect_user_id
        print("User persisted across restart and migration")
        return
    auth, original = call(
        "POST",
        prefix + "register",
        body={"email": args.email, "nickname": "Test Lawyer", "password": PASSWORD},
        expected=201,
    )
    assert auth["user"]["role"] == "lawyer" and original
    user_id = auth["user"]["user_id"]
    me, _ = call("GET", prefix + "me", token=auth["access_token"])
    assert me["user"]["user_id"] == user_id
    rotated, current = call("POST", prefix + "refresh", cookie=original)
    assert current and current != original and rotated["access_token"]
    error, _ = call("POST", prefix + "refresh", cookie=original, expected=401)
    assert error["error"]["code"] == "REFRESH_INVALID"
    call("POST", prefix + "logout", body={}, cookie=current, expected=204)
    error, _ = call("POST", prefix + "refresh", cookie=current, expected=401)
    assert error["error"]["code"] == "REFRESH_INVALID"
    auth, _ = call("POST", prefix + "login", body={"email": args.email, "password": PASSWORD})
    assert auth["user"]["user_id"] == user_id
    print(f"Gateway auth lifecycle passed; email={args.email} user_id={user_id}")


if __name__ == "__main__":
    main()
