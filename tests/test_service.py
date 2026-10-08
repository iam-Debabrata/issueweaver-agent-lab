from pathlib import Path

import pytest

from issueweaver import service
from issueweaver.providers import FixtureProvider
from issueweaver.sandbox import TrustedDemoRunner
from issueweaver.settings import Settings


class FakeGateway:
    published = []
    closed = False

    def __init__(self, repo, token):
        self.repo = repo
        self.token = token

    async def get_issue(self, number):
        return {"number": number, "title": "Add slugify", "body": "Handle repeated spaces"}

    async def base(self):
        return "main", "base_sha"

    async def checkout_archive(self, workspace, sha):
        (workspace / "README.md").write_text("trusted test target", encoding="utf-8")

    async def create_pr(self, number, title, branch, sha, files, *, run_summary):
        self.published.append((number, files, run_summary))
        return "https://github.com/owner/target/pull/17"

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_process_issue_dry_run_and_publish(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "GitHubGateway", FakeGateway)
    monkeypatch.setattr(service, "OpenAIProvider", lambda key, model: FixtureProvider())
    monkeypatch.setattr(service, "DockerSandbox", lambda image: TrustedDemoRunner())
    config = Settings(repo="owner/target", github_token="placeholder", allow_pr=True)
    dry = await service.process_issue(17, config, publish=False)
    assert dry["status"] == "passed_dry_run"
    assert not FakeGateway.published
    assert (tmp_path / "runs" / "issue-17.json").exists()
    live = await service.process_issue(17, config, publish=True)
    assert live["status"] == "pr_created"
    assert live["pr_url"].endswith("/17")
    assert FakeGateway.published[0][0] == 17


@pytest.mark.asyncio
async def test_process_issue_blocks_unapproved_publish():
    with pytest.raises(ValueError, match="GITHUB_ALLOW_PR"):
        await service.process_issue(1, Settings(), publish=True)
