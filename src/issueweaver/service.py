"""High-level engine: only a specifically configured repository can be changed."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .github import GitHubGateway
from .graph import build_graph
from .models import AgentState
from .providers import OpenAIProvider
from .sandbox import DockerSandbox
from .settings import Settings


async def process_issue(number: int, settings: Settings, *, publish: bool = False) -> dict:
    if publish and not settings.allow_pr:
        raise ValueError("GITHUB_ALLOW_PR=true required to create pull requests")
    gateway = GitHubGateway(settings.repo, settings.github_token)
    try:
        issue = await gateway.get_issue(number)
        branch, sha = await gateway.base()
        with tempfile.TemporaryDirectory(prefix="issueweaver-") as location:
            workspace = Path(location)
            await gateway.checkout_archive(workspace, sha)
            provider = OpenAIProvider(settings.openai_api_key, settings.openai_model)

            async def publisher(state: AgentState) -> str:
                return await gateway.create_pr(
                    number, state["issue_title"], branch, sha, state["files"],
                    run_summary="\n".join(state["trace"]),
                )

            graph = build_graph(provider, DockerSandbox(settings.sandbox_image), publisher)
            state = await graph.ainvoke({
                "issue_number": number,
                "issue_title": str(issue["title"]),
                "issue_body": str(issue.get("body") or ""),
                "workspace": workspace,
                "max_repairs": settings.max_repairs,
                "publish": publish,
                "trace": [],
            })
            summary = {
                "status": state["status"], "issue": number, "repo": settings.repo,
                "attempts": state.get("attempt", 0) + 1,
                "changed_paths": list(state.get("files", {})),
                "trace": state["trace"],
                "test_output": state.get("test").output if state.get("test") else "",
                "pr_url": state.get("pr_url", ""),
            }
            output = Path("runs")
            output.mkdir(exist_ok=True)
            (output / f"issue-{number}.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            return summary
    finally:
        await gateway.close()
