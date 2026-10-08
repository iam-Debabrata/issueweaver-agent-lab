from pathlib import Path

import pytest

from issueweaver.cli import run_demo
from issueweaver.graph import build_graph
from issueweaver.models import TestResult as RunResult
from issueweaver.providers import FixtureProvider


@pytest.mark.asyncio
async def test_demo_repairs_initial_test_failure():
    result = await run_demo()
    assert result["status"] == "passed_dry_run"
    assert result["repairs"] == 1
    assert any("Tester: FAIL" in item for item in result["trace"])
    assert any("Tester: PASS" in item for item in result["trace"])
    assert sorted(result["paths"]) == ["tests/test_utils.py", "utils.py"]


class AlwaysFail:
    async def run(self, root):
        return RunResult(passed=False, exit_code=1, output="Failure")


@pytest.mark.asyncio
async def test_budget_ends_failure_without_pr(tmp_path: Path):
    graph = build_graph(FixtureProvider(), AlwaysFail())
    outcome = await graph.ainvoke({
        "issue_title": "bug", "issue_body": "repair", "workspace": tmp_path,
        "trace": [], "max_repairs": 1, "publish": True,
    })
    assert outcome["status"] == "tests_failed"
    assert outcome["attempt"] == 1
    assert "pr_url" not in outcome


@pytest.mark.asyncio
async def test_publisher_only_after_green_tests(tmp_path: Path):
    class AlwaysPass:
        async def run(self, root):
            return RunResult(passed=True, exit_code=0, output="2 passed")

    async def publish(state):
        assert state["test"].passed
        return "https://github.com/sample/repo/pull/5"

    graph = build_graph(FixtureProvider(), AlwaysPass(), publish)
    result = await graph.ainvoke({
        "issue_title": "bug", "issue_body": "please", "workspace": tmp_path,
        "trace": [], "max_repairs": 0, "publish": True,
    })
    assert result["status"] == "pr_created"
    assert result["pr_url"].endswith("/5")


@pytest.mark.asyncio
async def test_infrastructure_errors_do_not_waste_repair_budget(tmp_path: Path):
    class Unavailable:
        async def run(self, root):
            return RunResult(passed=False, exit_code=124, output="docker daemon absent")

    graph = build_graph(FixtureProvider(), Unavailable())
    result = await graph.ainvoke({
        "issue_title": "build utility", "issue_body": "fix", "workspace": tmp_path,
        "trace": [], "max_repairs": 4, "publish": False,
    })
    assert result["attempt"] == 0
    assert "infrastructure" in result["trace"][-1]
