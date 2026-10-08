"""HMAC-verified GitHub Issues webhook (explicit label gating; no surprise PRs)."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from .service import process_issue
from .settings import Settings

Job = Callable[[int, Settings], Awaitable[dict]]


def verify_signature(raw: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class DeliveryLog:
    """Deduplicate payloads across app restarts; one process per SQLite DB."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS deliveries "
            "(delivery TEXT PRIMARY KEY, issue INTEGER NOT NULL, status TEXT NOT NULL)"
        )
        self.db.commit()

    def register(self, delivery: str, issue: int) -> bool:
        cursor = self.db.execute(
            "INSERT OR IGNORE INTO deliveries VALUES (?, ?, 'queued')", (delivery, issue)
        )
        self.db.commit()
        return cursor.rowcount == 1

    def status(self, delivery: str, value: str) -> None:
        self.db.execute("UPDATE deliveries SET status=? WHERE delivery=?", (value, delivery))
        self.db.commit()


def create_app(
    settings: Settings | None = None, *, job: Job | None = None, db_path: Path | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    database = DeliveryLog(db_path or Path(os.getenv("ISSUEWEAVER_DB_PATH", "issueweaver-deliveries.sqlite3")))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            database.db.close()

    app = FastAPI(title="IssueWeaver webhook", version="0.1.0", lifespan=lifespan)

    async def default_job(issue: int, config: Settings) -> dict:
        return await process_issue(issue, config, publish=config.allow_pr)

    worker = job or default_job

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": "publish" if settings.allow_pr else "dry-run"}

    async def run_job(delivery: str, issue: int) -> None:
        try:
            database.status(delivery, "running")
            result = await worker(issue, settings)
            database.status(delivery, str(result.get("status", "finished")))
        except Exception:
            database.status(delivery, "error")
            raise

    @app.post("/webhook/github", status_code=202)
    async def github_webhook(request: Request, background_tasks: BackgroundTasks):
        raw = await request.body()
        if len(raw) > 256_000:
            raise HTTPException(status_code=413, detail="Payload too large")
        if not verify_signature(
            raw, request.headers.get("X-Hub-Signature-256"), settings.webhook_secret
        ):
            raise HTTPException(status_code=403, detail="Invalid signature")
        if request.headers.get("X-GitHub-Event") != "issues":
            return {"accepted": False, "reason": "not an issues event"}
        try:
            payload = await request.json()
            repo = payload["repository"]["full_name"]
            action = payload["action"]
            issue = payload["issue"]
            issue_no = issue["number"]
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid issue payload") from exc
        if repo != settings.repo:
            raise HTTPException(status_code=403, detail="Repository not on allowlist")
        if action != "labeled" or payload.get("label", {}).get("name") != settings.webhook_label:
            return {"accepted": False, "reason": "missing opt-in label event"}
        if "pull_request" in issue:
            return {"accepted": False, "reason": "not a regular issue"}
        delivery = request.headers.get("X-GitHub-Delivery", "")
        if not delivery or len(delivery) > 128:
            raise HTTPException(status_code=400, detail="Invalid delivery ID")
        if not database.register(delivery, int(issue_no)):
            return {"accepted": False, "reason": "duplicate delivery"}
        background_tasks.add_task(run_job, delivery, int(issue_no))
        return {"accepted": True, "delivery": delivery, "issue": issue_no}

    return app


app = create_app()
