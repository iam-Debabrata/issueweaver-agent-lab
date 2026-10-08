import hashlib
import hmac

from fastapi.testclient import TestClient

from issueweaver.api import create_app, verify_signature
from issueweaver.settings import Settings


def signature(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_official_github_hmac_vector():
    assert signature("It's a Secret to Everybody", b"Hello, World!") == (
        "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
    )
    assert verify_signature(b"Hello, World!", signature("secret", b"Hello, World!"), "secret")
    assert not verify_signature(b"Hello, World!", "sha256=abcd", "secret")
    assert not verify_signature(b"a", None, "secret")
    assert not verify_signature(b"a", "sha256=abc", "")


def test_webhook_authorization_and_dedup(tmp_path):
    seen = []

    async def job(issue, settings):
        seen.append(issue)
        return {"status": "passed_dry_run"}

    config = Settings(repo="owner/target", webhook_secret="secret")
    app = create_app(config, job=job, db_path=tmp_path / "deliveries.sqlite3")
    payload = {"action": "labeled", "repository": {"full_name": "owner/target"},
               "issue": {"number": 5}, "label": {"name": "swarm-ready"}}
    import json

    raw = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": signature("secret", raw),
               "X-GitHub-Event": "issues", "X-GitHub-Delivery": "id-1"}
    with TestClient(app) as client:
        assert client.get("/health").json()["mode"] == "dry-run"
        assert client.post("/webhook/github", content=raw).status_code == 403
        r = client.post("/webhook/github", content=raw, headers=headers)
        assert r.status_code == 202 and r.json()["accepted"]
        assert client.post("/webhook/github", content=raw, headers=headers).json()["reason"] == "duplicate delivery"
        assert seen == [5]
        wrong_repo = dict(payload, repository={"full_name": "owner/other"})
        encoded = json.dumps(wrong_repo).encode()
        assert client.post("/webhook/github", content=encoded,
            headers=dict(headers, **{"X-Hub-Signature-256": signature("secret", encoded)})).status_code == 403
        different = dict(payload, label={"name": "ignore"})
        encoded = json.dumps(different).encode()
        assert not client.post("/webhook/github", content=encoded,
            headers=dict(headers, **{"X-Hub-Signature-256": signature("secret", encoded),
                                  "X-GitHub-Delivery": "id-2"})).json()["accepted"]


def test_invalid_event_and_payload(tmp_path):
    config = Settings(repo="a/b", webhook_secret="secret")
    app = create_app(config, db_path=tmp_path / "x.db")
    with TestClient(app) as client:
        raw = b"{}"
        base = {"X-Hub-Signature-256": signature("secret", raw), "X-GitHub-Delivery": "id"}
        assert not client.post("/webhook/github", content=raw, headers={**base,
            "X-GitHub-Event": "ping"}).json()["accepted"]
        assert client.post("/webhook/github", content=raw, headers={**base,
            "X-GitHub-Event": "issues"}).status_code == 400
        assert client.post("/webhook/github", content=b"x" * 256001).status_code == 413
