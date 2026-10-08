"""Small explicit configuration surface; secrets only come from the environment."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: str = ".env") -> None:
    """Load basic KEY=VALUE entries without shell execution or variable expansion."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    repo: str = ""
    github_token: str = ""
    webhook_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    allow_pr: bool = False
    webhook_label: str = "swarm-ready"
    sandbox_image: str = "issueweaver-pytest:local"
    max_repairs: int = 2

    @classmethod
    def from_env(cls) -> Settings:
        load_env_file()
        limit = max(0, min(4, int(os.getenv("MAX_REPAIRS", "2"))))
        return cls(
            repo=os.getenv("GITHUB_REPOSITORY", "").strip(),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            allow_pr=os.getenv("GITHUB_ALLOW_PR", "false").lower() == "true",
            webhook_label=os.getenv("WEBHOOK_LABEL", "swarm-ready"),
            sandbox_image=os.getenv("SANDBOX_IMAGE", "issueweaver-pytest:local"),
            max_repairs=limit,
        )
