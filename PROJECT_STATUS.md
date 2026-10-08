# Verification record - 2026-10-08

## Completed and checked in this chat

- Python source: architect/coder/tester/repair/review/publish graph.
- FastAPI endpoint and signed GitHub issue label gating.
- Restricted Docker runner configuration plus trusted sample-only local runner.
- GitHub REST client, safely scoped file writes, and draft PR publishing flow.
- Pytest security, integration-mock and behavior tests: **39 passed** after
  Windows subprocess environment regression fixes.
- `pytest --cov=issueweaver` measured **91%** statement coverage (Python 3.13).
- The local `python -m issueweaver demo` completed FAIL -> REPAIR -> PASS.
- The trusted demo runner retains Windows `SystemRoot` and avoids loading
  unrelated Pytest plugins in its fixture subprocess. A synthetic WinError
  10106 no longer consumes the code-repair budget.
- Python `compileall` succeeded for source and tests.
- PDF learning manual and PDF command guide were rendered and inspected.

## Not verified here - do NOT claim as completed

- New private GitHub repository created or pushed. This chat's GitHub connector
  cannot create repositories. Your existing repository was NOT touched.
- Actual `langgraph` package run. This environment lacks the package and
  cannot download it; the local tests use the documented graph compatibility
  shim. Production installs the real package via `pip install -e '.[dev]'`.
- Running tests in a live Docker daemon (not available here).
- Calling OpenAI with a real API key / paid model usage.
- Receiving a public HTTPS GitHub webhook or publishing a live draft PR.
- GitHub Actions CI running on GitHub (new repo does not yet exist).
- Running Ruff lint: Ruff package unavailable locally; CI is configured to
  install Ruff and run its check on the new repository.
- A live Windows Python 3.13 rerun has not been executed in this Linux
  environment; Windows regression behavior was tested with a simulated error.

## Safeguards / notes

The private repository publishing scripts refuse overwriting an existing repo;
all sample credentials are placeholders. No `.env` is included. The live bot is
restricted to exactly one repo chosen in `GITHUB_REPOSITORY`, no merge, always
DRAFT PRs only when publishing is explicitly enabled and tests pass. Docker
is defense-in-depth, not VM-grade isolation. Review results before public launch.
