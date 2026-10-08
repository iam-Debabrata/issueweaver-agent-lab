from pathlib import Path

import pytest

from issueweaver.models import Plan, Proposal
from issueweaver.workspace import apply_proposal, source_context, valid_relative_path


@pytest.mark.parametrize("path", [
    "../outside.py", ".github/workflows/ci.py", "/tmp/hack.py", "x/../y.py",
    ".env", "data.json", "x\\evil.py", "__pycache__/a.py", "./hidden.py",
    "one/.secrets/s.py", "readme.md", "bad name.py", "",
])
def test_forbidden_paths(path):
    assert not valid_relative_path(path)


@pytest.mark.parametrize("path", ["app.py", "tests/test_app.py", "src/pkg/feature_v2.py"])
def test_allowed_paths(path):
    assert valid_relative_path(path)


def test_apply_proposal_atomic_path_validation(tmp_path: Path):
    proposal = Proposal(summary="update code", files={"safe.py": "x = 1\n", "../evil.py": "x=2"})
    with pytest.raises(ValueError):
        apply_proposal(tmp_path, proposal)
    assert not (tmp_path / "safe.py").exists()


def test_apply_blocks_symlink_escape(tmp_path: Path):
    target = tmp_path.parent / "escape_out"
    target.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        apply_proposal(tmp_path, Proposal(summary="bad write", files={"link/a.py": "x=3"}))
    assert not (target / "a.py").exists()


def test_context_bounds_and_writes(tmp_path: Path):
    files = apply_proposal(tmp_path, Proposal(summary="valid write", files={
        "src/a.py": "print('hello')\n", "tests/test_a.py": "assert True\n",
    }))
    assert len(files) == 2
    context = source_context(tmp_path, max_files=1, max_chars=8)
    assert context.startswith("FILE: src/a.py")
    assert "tests/test_a.py" not in context


def test_plan_validates_empty_list():
    with pytest.raises(ValueError):
        Plan(rationale="enough", tasks=[])
