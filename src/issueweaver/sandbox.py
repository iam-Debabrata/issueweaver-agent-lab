"""Docker-only sandbox for untrusted code; local runner for bundled fixture only."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from .models import TestResult


class DockerSandbox:
    """A restricted Docker container is defense-in-depth, not a hardened VM boundary."""

    def __init__(self, image: str = "issueweaver-pytest:local", timeout: int = 45):
        self.image = image
        self.timeout = timeout

    async def run(self, root: Path) -> TestResult:
        return await asyncio.to_thread(self._run_sync, root)

    def _run_sync(self, root: Path) -> TestResult:
        client = None
        container = None
        try:
            import docker

            root = root.resolve(strict=True)
            root.chmod(0o755)  # allow unprivileged container to read temp workspace
            client = docker.from_env()
            container = client.containers.run(
                self.image,
                command=["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                detach=True,
                network_disabled=True,
                read_only=True,
                user="10001:10001",
                working_dir="/workspace",
                volumes={str(root): {"bind": "/workspace", "mode": "ro"}},
                tmpfs={"/tmp": "rw,noexec,nosuid,size=32m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                pids_limit=64,
                mem_limit="256m",
                nano_cpus=1_000_000_000,
                environment={
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": "/workspace",
                    "HOME": "/tmp",
                },
            )
            response = container.wait(timeout=self.timeout)
            code = int(response.get("StatusCode", 1))
            log = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            return TestResult(passed=code == 0, exit_code=code, output=log[-8000:])
        except Exception as exc:
            return TestResult(passed=False, exit_code=124, output=f"Sandbox error: {type(exc).__name__}")
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            if client is not None:
                client.close()



class TrustedDemoRunner:
    """Execute only bundled example code; NEVER use this on downloaded repositories."""

    @staticmethod
    def _child_environment(root: Path) -> dict[str, str]:
        """Keep Windows runtime settings without exposing credentials to fixture tests.

        A nearly empty ``env`` breaks Windows Python's ``_overlapped`` import:
        Winsock providers need SystemRoot to find their DLLs (WinError 10106).
        Only the trusted built-in demonstration uses this local process runner.
        """
        required_windows_keys = {"SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT"}
        env = {key: value for key, value in os.environ.items()
               if key.upper() in required_windows_keys}
        env.update({
            "PATH": "",
            "PYTHONPATH": str(root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        })
        return env

    async def run(self, root: Path) -> TestResult:
        completed = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            env=self._child_environment(root),
            check=False,
        )
        text = (completed.stdout + "\n" + completed.stderr)[-8000:]
        if "WinError 10106" in text and "_overlapped" in text:
            return TestResult(
                passed=False, exit_code=124,
                output="Windows Pytest infrastructure error (WinError 10106): "
                       "the subprocess could not initialize Winsock.\n" + text,
            )
        return TestResult(passed=completed.returncode == 0, exit_code=completed.returncode, output=text)
