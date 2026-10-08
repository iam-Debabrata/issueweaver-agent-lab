"""IssueWeaver commands. Only `demo` runs without GitHub/OpenAI/Docker access."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from .graph import build_graph
from .providers import FixtureProvider
from .sandbox import TrustedDemoRunner
from .service import process_issue
from .settings import Settings


async def run_demo() -> dict:
    source = Path(__file__).resolve().parents[2] / "examples" / "sample_target"
    with tempfile.TemporaryDirectory(prefix="issueweaver-fixture-") as location:
        root = Path(location)
        shutil.copytree(source, root, dirs_exist_ok=True)
        graph = build_graph(FixtureProvider(), TrustedDemoRunner())
        state = await graph.ainvoke({
            "issue_title": "Normalize whitespace in slugify", "issue_body": "Turn text into slugs",
            "workspace": root, "max_repairs": 2, "publish": False, "trace": [],
        })
        return {
            "status": state["status"], "repairs": state["attempt"],
            "trace": state["trace"], "test_output": state["test"].output,
            "paths": list(state["files"]),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="IssueWeaver: issue-to-PR with test gates")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("demo", help="Local, fixture-only test-and-repair demo")
    issue = subs.add_parser("issue", help="Run an issue from the configured GitHub repo")
    issue.add_argument("--number", type=int, required=True)
    issue.add_argument("--publish", action="store_true", help="Open a draft PR after tests pass")
    args = parser.parse_args()
    if args.command == "demo":
        result = asyncio.run(run_demo())
    else:
        result = asyncio.run(process_issue(
            args.number, Settings.from_env(), publish=args.publish
        ))
    print(json.dumps(result, indent=2))
    if result["status"] not in ("passed_dry_run", "pr_created"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
