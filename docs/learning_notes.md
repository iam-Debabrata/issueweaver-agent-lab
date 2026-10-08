# Learning notes: from one prompt to a test-gated agent system

## 1. What makes this an agent system?

A traditional script follows fixed rules. A single LLM prompt answers a question once.
IssueWeaver has **a plan, memory (state), actions, feedback, and a stopping condition**.
The Architect plans the change; Coder writes typed file proposals; Tester runs pytest;
Repair uses failure output; Reviewer gates publication. In the live mode each
Architect/Coder/Repair step uses a real model call. In the free demo the provider
is deterministic to demonstrate the control flow without needing API credentials.

**State** is a dictionary (`AgentState`) containing the issue, workspace, planned
tasks, candidate files, previous tests, retry counter, and decision trace. LangGraph's
`StateGraph` connects nodes and conditions. A node returns a *partial state update*.
A conditional edge reads the test result and decides where execution goes next.

**Example**: issue: "Add a slugify(text) function." The first candidate uses
`text.lower().replace(' ', '-')`. That fails for repeated spaces.
The test expects `slugify('  Hello   World  ') == 'hello-world'`.
Repair changes the implementation to `'-'.join(text.lower().split())`.
The second pytest execution passes. This is **not** a guarantee that the output is
semantically correct in general; the tests decide which requirements are checked.

## 2. How `MAX_REPAIRS` is enforced

The workflow begins at `attempt=0`. Each failed test with remaining budget returns
to Repair and increments `attempt`. If `max_repairs=2`, there are at most **three**
test executions (original + two repairs). The loop terminates on pass or exhaustion.
This finite budget protects latency and API expense.

## 3. Why structured proposals beat shell commands

Instead of asking the model to run arbitrary terminal commands, the provider returns:

```json
{
  "summary": "Implement slugification and add edge-case tests",
  "files": {
    "utils.py": "def slugify(text: str) -> str:\n    return '-'.join(text.lower().split())\n"
  }
}
```

Pydantic validates the structure. The write gate rejects absolute paths, traversal,
config/secrets/workflow directories, symlinks and non-Python files. At most six files
are allowed per model response and each file is capped at 32 KB. This is useful
but not enough: malicious executable Python can still attack inside its sandbox.

## 4. How the test sandbox works

The orchestrator runs on a **trusted host**, and uses Docker SDK to create a
separate one-shot test container. The Docker test container has:

- no network, read-only root, read-only code volume;
- dropped Linux capabilities, no-new-privileges and non-root UID;
- 256 MB memory, 1 CPU, max 64 PIDs;
- 45-second wait timeout, and forced deletion after the run.

It runs `python -m pytest -q -p no:cacheprovider` in the project snapshot.
The `TrustedDemoRunner` is only for the bundled safe tutorial, **not** for live
GitHub repositories. A Docker container shares the host kernel and the daemon
has powerful host access; for an internet-facing service, use VM-level
isolation, egress controls, strict tokens and a real queue.

## 5. HMAC webhook validation

A GitHub webhook payload is just an HTTP request. Verify its authenticity **before**
using it:

`signature = 'sha256=' + HMAC_SHA256(secret, raw_request_body).hexdigest()`

Compare this with `X-Hub-Signature-256` in constant time. Then check that the
`X-GitHub-Event` is `issues`, the action is `labeled`, the label is `swarm-ready`,
and the repository matches the configured allowlist exactly. SQLite prevents
processing the same delivery ID twice. It is not a crash-proof job queue.

## 6. How a draft PR is made without pushing to main

The GitHub adapter uses REST and Git data APIs to read the issue, snapshot a
bounded ZIP of the repository, stage Git blobs for changed files, create a tree,
make a commit, create a **new branch**, and open a **draft PR**. The reference
`main` branch is never updated. Publishing requires both an explicit CLI flag
and the env setting `GITHUB_ALLOW_PR=true` (or a signed, opted-in webhook).

The workflow never merges automatically: human review and CI are essential.

## 7. Engineering tradeoffs worth discussing in interviews

**Why LangGraph instead of multiple independent prompts?** State transitions
and retry conditions are explicit and testable. **Why typed JSON?** File writes
become machine-validatable. **Why Docker?** Untrusted test execution must be
separated from API keys and source control credentials. **Why cap retries?** An
agent loop needs a cost/latency boundary. **Why draft PRs?** Tests measure only
asserted behavior; CI and a human catch oversights. **What's missing for a
production system?** Durable queue, observability/tracing, VM isolation,
per-repo dependency environments, model cost limits, policy AST analysis,
red-team tests, secret scanning, provider resilience and benchmark evidence.

## 8. Your extension exercises

1. Persist a full state checkpoint after every node and resume a failed job.
2. Add a separate static-analysis node using Ruff and Bandit inside sandbox.
3. Include AST-based edits rather than full-file replacements.
4. Report pass@1, repair success rate, median runtime, and per-issue model spend.
5. Run a small benchmark across 10 safe synthetic issues; publish the exact results.
6. Replace Docker runner with a separate microVM worker, keeping the same interface.

Interview-ready claim after *live verification*: "I built a Python/LangGraph
issue-to-draft-PR pipeline with typed agent outputs, Docker-isolated pytest,
retry-budgeted repair, verified webhooks, and multi-version CI."

**Never claim:** "production-safe, zero hallucinations, supports any repository,
or guaranteed bug-free." Those assertions are untested.
