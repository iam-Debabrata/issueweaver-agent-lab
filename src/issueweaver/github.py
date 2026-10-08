"""GitHub REST adapter: issue ingestion, safe snapshot, and atomic PR creation."""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath

import httpx

from .workspace import valid_relative_path

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubGateway:
    def __init__(self, repo: str, token: str, client: httpx.AsyncClient | None = None):
        if not _REPO.fullmatch(repo):
            raise ValueError("Repository must be owner/name")
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self.repo = repo
        self.client = client or httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            follow_redirects=True,
            timeout=40.0,
        )
        self.owns_client = client is None

    async def close(self) -> None:
        if self.owns_client:
            await self.client.aclose()

    async def api(self, method: str, endpoint: str, **kwargs):
        response = await self.client.request(method, f"/repos/{self.repo}/{endpoint}", **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_issue(self, number: int) -> dict:
        if number < 1:
            raise ValueError("Issue number must be positive")
        issue = await self.api("GET", f"issues/{number}")
        if "pull_request" in issue:
            raise ValueError("Refusing to process a pull request as an issue")
        return issue

    async def base(self) -> tuple[str, str]:
        info = await self.api("GET", "")
        branch = info["default_branch"]
        head = await self.api("GET", f"branches/{branch}")
        return branch, head["commit"]["sha"]

    async def checkout_archive(self, root: Path, sha: str) -> None:
        response = await self.client.get(f"/repos/{self.repo}/zipball/{sha}")
        response.raise_for_status()
        if len(response.content) > 15_000_000:
            raise ValueError("Repository archive exceeds 15 MB")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            entries = archive.infolist()
            if len(entries) > 400:
                raise ValueError("Repository exceeds 400 archive entries")
            total = 0
            for item in entries:
                name = PurePosixPath(item.filename)
                rel = PurePosixPath(*name.parts[1:])
                if not rel.parts:
                    continue
                if (name.is_absolute() or ".." in rel.parts or "\\" in item.filename
                        or (item.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("Unsafe repository archive entry")
                total += item.file_size
                if total > 30_000_000:
                    raise ValueError("Uncompressed archive exceeds 30 MB")
                dest = root.joinpath(*rel.parts)
                if not dest.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Archive path escapes workspace")
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.read(item))

    async def create_pr(
        self, issue_number: int, issue_title: str, base_branch: str, base_sha: str,
        files: dict[str, str], *, run_summary: str,
    ) -> str:
        if not files or not all(valid_relative_path(name) for name in files):
            raise ValueError("Attempt to publish forbidden paths")
        commit_meta = await self.api("GET", f"git/commits/{base_sha}")
        entries = []
        for path, content in files.items():
            blob = await self.api("POST", "git/blobs", json={
                "content": content, "encoding": "utf-8",
            })
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree = await self.api("POST", "git/trees", json={
            "base_tree": commit_meta["tree"]["sha"], "tree": entries,
        })
        commit = await self.api("POST", "git/commits", json={
            "message": f"feat: address issue #{issue_number} via test-gated agents",
            "tree": tree["sha"], "parents": [base_sha],
        })
        branch = f"issueweaver/issue-{issue_number}-{uuid.uuid4().hex[:8]}"
        await self.api("POST", "git/refs", json={
            "ref": f"refs/heads/{branch}", "sha": commit["sha"],
        })
        pr = await self.api("POST", "pulls", json={
            "title": f"[IssueWeaver] {issue_title[:100]}",
            "body": (
                f"Closes #{issue_number}\n\nAutomated proposal - **human review required**.\n\n"
                f"Run summary:\n```\n{run_summary[:2000]}\n```\n\n"
                "Tests were executed in a restricted Docker sandbox. Review code and CI results."
            ),
            "head": branch, "base": base_branch, "draft": True,
        })
        return str(pr["html_url"])
