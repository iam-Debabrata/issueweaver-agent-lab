import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from issueweaver.models import Plan
from issueweaver.providers import OpenAIProvider
from issueweaver.sandbox import DockerSandbox, TrustedDemoRunner
from issueweaver.settings import Settings


def test_settings(monkeypatch):
    monkeypatch.setenv("GITHUB_ALLOW_PR", "true")
    monkeypatch.setenv("MAX_REPAIRS", "99")
    config = Settings.from_env()
    assert config.allow_pr
    assert config.max_repairs == 4


def test_live_provider_requires_key():
    with pytest.raises(ValueError):
        OpenAIProvider("", "test-model")


@pytest.mark.asyncio
async def test_openai_provider_output_contract():
    values = iter(['{"rationale":"we should test this","tasks":["implement"]}',
                   '{"summary":"implement feature","files":{"main.py":"x=1"}}'])

    class FakeCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(values)))])

    provider = object.__new__(OpenAIProvider)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider.model = "fake"
    plan = await provider.plan("title", "body", "context")
    assert isinstance(plan, Plan)
    proposal = await provider.code("title", "body", plan, "source", 0, "")
    assert proposal.files["main.py"] == "x=1"


@pytest.mark.asyncio
async def test_docker_options_without_running_a_real_container(monkeypatch, tmp_path: Path):
    recorded = {}

    class Container:
        def wait(self, timeout):
            recorded["timeout"] = timeout
            return {"StatusCode": 0}

        def logs(self, **kwargs):
            return b"2 passed"

        def remove(self, force=False):
            recorded["removed"] = force

    class Client:
        containers = None

        def __init__(self):
            self.containers = SimpleNamespace(run=self.run)

        def run(self, image, **kwargs):
            recorded.update(kwargs)
            return Container()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "docker", SimpleNamespace(from_env=Client))
    result = await DockerSandbox("testimage").run(tmp_path)
    assert result.passed
    assert recorded["network_disabled"] is True
    assert recorded["read_only"] is True
    assert recorded["cap_drop"] == ["ALL"]
    assert recorded["volumes"][str(tmp_path)]["mode"] == "ro"
    assert recorded["removed"]


def test_load_env_file_without_overwriting_existing(monkeypatch, tmp_path):
    from issueweaver.settings import load_env_file

    envfile = tmp_path / ".env"
    envfile.write_text('# comment\nGITHUB_REPOSITORY=student/test-repo\n'
                       'BAD!KEY=skipped\nOPENAI_MODEL="a-model"\n', encoding="utf-8")
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "already-here")
    load_env_file(str(envfile))
    assert os.environ["GITHUB_REPOSITORY"] == "student/test-repo"
    assert os.environ["OPENAI_MODEL"] == "already-here"


def test_demo_runner_preserves_windows_systemroot_but_not_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("SystemRoot", "C:\\Windows")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    env = TrustedDemoRunner._child_environment(tmp_path)
    assert env["SystemRoot"] == "C:\\Windows"
    assert env["PYTHONPATH"] == str(tmp_path)
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert "OPENAI_API_KEY" not in env


@pytest.mark.asyncio
async def test_windows_winsock_startup_error_is_not_a_code_failure(monkeypatch, tmp_path):
    from issueweaver.graph import build_graph
    from issueweaver.providers import FixtureProvider

    def broken_windows_pytest(*args, **kwargs):
        return SimpleNamespace(
            stdout="", stderr="import _overlapped\nOSError: [WinError 10106] provider failed",
            returncode=1,
        )

    monkeypatch.setattr("issueweaver.sandbox.subprocess.run", broken_windows_pytest)
    graph = build_graph(FixtureProvider(), TrustedDemoRunner())
    result = await graph.ainvoke({
        "issue_title": "demo", "issue_body": "demo", "workspace": tmp_path,
        "trace": [], "max_repairs": 2, "publish": False,
    })
    assert result["attempt"] == 0
    assert result["test"].exit_code == 124
    assert "infrastructure" in result["trace"][-1]
