"""Safely constrain an LLM's file-writing permissions."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .models import Proposal

_ALLOWED = re.compile(r"^[a-zA-Z0-9_./-]+$")
_BANNED = {".git", ".github", ".venv", "__pycache__", "node_modules", ".ssh"}


def valid_relative_path(name: str) -> bool:
    if not name or len(name) > 160 or not _ALLOWED.fullmatch(name) or "\\" in name:
        return False
    if name.startswith("./") or "//" in name or name.endswith("/"):
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in _BANNED or part in ("", ".", "..") for part in path.parts):
        return False
    if any(part.startswith(".") for part in path.parts):
        return False
    return path.suffix == ".py"


def apply_proposal(root: Path, proposal: Proposal) -> dict[str, str]:
    """Validate *all* writes before touching the filesystem."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Workspace must be a normal directory")
    for name, content in proposal.files.items():
        if not valid_relative_path(name):
            raise ValueError(f"Forbidden path: {name!r}")
        if len(content.encode("utf-8")) > 32_000:
            raise ValueError(f"File too large: {name}")
        dest = root / name
        if any(parent.is_symlink() for parent in (dest, *dest.parents) if parent != root and root in parent.parents):
            raise ValueError(f"Symlink traversal blocked: {name}")
        if dest.exists() and (not dest.is_file() or dest.is_symlink()):
            raise ValueError(f"Cannot overwrite special file: {name}")
        if not dest.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Path escapes workspace: {name}")
    for name, content in proposal.files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return proposal.files.copy()


def source_context(root: Path, *, max_files: int = 12, max_chars: int = 1200) -> str:
    """Small, bounded file snapshot; data only, never executable instructions."""
    sections: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if not valid_relative_path(rel) or path.is_symlink() or not path.is_file():
            continue
        sections.append(f"FILE: {rel}\n{path.read_text(encoding='utf-8', errors='replace')[:max_chars]}")
        if len(sections) >= max_files:
            break
    return "\n\n".join(sections) or "(no existing Python source files)"
