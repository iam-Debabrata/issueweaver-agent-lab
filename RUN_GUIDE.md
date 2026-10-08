# IssueWeaver Lab - complete start-to-finish run guide

**Audience:** MS in AI student building a private, interview-ready GitHub project.  
**Repository name reserved in these instructions:** `iam-Debabrata/issueweaver-agent-lab`.  
**Rule:** the scripts refuse to overwrite an existing remote or repository.

## 0. Know what is real and what is a teaching simulation

The no-key `demo` uses a **preprogrammed FixtureProvider** and a trusted local
sample. It proves workflow plumbing, test-gating, failure feedback, and repair.
The live `issue` command uses LangGraph, a real OpenAI model, Docker and GitHub.
It requires your own credentials and a small Python target repo. Unit tests mock
the external APIs; their success is not a substitute for a real live test.

## 1. Get the project onto your computer

Download the `IssueWeaver_Lab.zip` file from the chat, extract it, and open
Terminal (macOS/Linux) or PowerShell (Windows) **inside `IssueWeaver_Lab/`**.
Check the folder contains `pyproject.toml`, `src`, `tests`, `Dockerfile`.

### Windows PowerShell - copy/paste one block at a time

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m issueweaver demo
python -m pytest -q --cov=issueweaver --cov-report=term-missing
```

If PowerShell blocks venv activation, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and retry it.
Install Python 3.11+ from python.org if `python --version` fails.

### macOS/Linux - copy/paste one block at a time

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m issueweaver demo
python -m pytest -q --cov=issueweaver --cov-report=term-missing
```

**Expected demo:** one `Tester: FAIL`, one `Repair`, then `Tester: PASS`,
and final `"status": "passed_dry_run"`. No GitHub tokens or Docker are needed.
Internet is needed for first-time package installation.

## 2. Upload the code to your NEW PRIVATE GitHub repo

Install Git and GitHub CLI (`gh`): on Windows, `winget install Git.Git` and
`winget install GitHub.cli` (then reopen PowerShell). Sign in:

```powershell
gh auth login
```

Use your **own** account `iam-Debabrata` when prompted. From this project
folder, create the new *private* repository and push its first commit:

```powershell
.\scripts\publish_private.ps1
```

macOS/Linux, after installing Git and `gh`:

```bash
gh auth login
bash scripts/publish_private.sh
```

The script checks that the target repo does not already exist and the current
folder has no `.git`. It only creates
`https://github.com/iam-Debabrata/issueweaver-agent-lab`. If a repository of
this name already exists, stop and choose a new unused name in the script.

**Important:** repository creation is currently unavailable to the GitHub
integration in this chat; that login/upload step cannot be performed for you
here. The script does not alter any existing repository.

## 3. Real Docker sandbox (for untrusted code)

Install Docker Desktop on Windows/macOS or Docker Engine on Linux, start it,
and verify:

```bash
docker version
docker build -t issueweaver-pytest:local sandbox/
```

This creates a *separate* runner image; your application Dockerfile is for
hosting the API. The runner can import Python standard-library modules and
pytest but **does not install project-specific dependencies**. Add dependencies
to a reviewed custom runner image if your test target requires them.

## 4. Make an OPTIONAL fresh private playground repo for testing

This avoids ever modifying your existing projects. From a terminal with `gh`
authenticated (only if you want to test live issue-to-PR):

```bash
gh repo create iam-Debabrata/issueweaver-playground --private --add-readme
gh issue create --repo iam-Debabrata/issueweaver-playground \
  --title "Add a Python slugify(text) function with tests" \
  --body "Create utils.py with slugify(text) that normalizes whitespace and lowercases words. Add pytest tests for repeated whitespace."
```

On **Windows PowerShell** keep the `gh issue create` command all on one line
(do not paste the trailing `\` continuation characters):

```powershell
gh issue create --repo iam-Debabrata/issueweaver-playground --title "Add a Python slugify(text) function with tests" --body "Create utils.py with slugify(text) that normalizes whitespace and lowercases words. Add pytest tests for repeated whitespace."
```

Read the number printed by GitHub (likely 1; use the actual number).
Never point `GITHUB_REPOSITORY` at your old code repository.

## 5. Add credentials in ignored `.env` file

Windows: `Copy-Item .env.example .env`  
macOS/Linux: `cp .env.example .env`

Open `.env` in a text editor, then set:

```dotenv
GITHUB_REPOSITORY=iam-Debabrata/issueweaver-playground
GITHUB_TOKEN=YOUR_FINE_GRAINED_GITHUB_TOKEN
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini
GITHUB_ALLOW_PR=false
GITHUB_WEBHOOK_SECRET=YOUR_LONG_RANDOM_SECRET
```

GitHub token: GitHub Settings -> Developer settings -> Personal access tokens ->
Fine-grained tokens. Choose **only the new playground repository** and grant
Contents (read/write), Pull requests (read/write), Metadata (read) and Issues
(read). Do not give access to your other repositories. OpenAI API usage is
billed separately from ChatGPT subscriptions.

`.env` is ignored by Git. The built-in parser loads simple `KEY=VALUE` pairs,
not shell statements or variable interpolation. Verify it before publishing.

## 6. Real issue processing: first dry-run, then draft PR

Run from the project directory with the Python environment active and Docker running:

```bash
python -m issueweaver issue --number 1
```

Replace `1` with your actual issue number. It will fetch your chosen repo,
use the model to plan/write code, invoke Docker pytest, attempt at most two
repairs, and save `runs/issue-1.json` (ignored by Git). Dry-run never creates
a branch or PR. No automatic write to any existing repository occurs.

After inspecting the generated report and reviewing what would change,
edit `.env` to `GITHUB_ALLOW_PR=true` and run:

```bash
python -m issueweaver issue --number 1 --publish
```

Only if tests are green, the tool will create a new feature branch and a
**draft pull request** in the repository named in `.env`; it never merges it.
Read the PR diff, wait for CI, then perform the human review yourself.

## 7. The FastAPI webhook listener (optional automatic trigger)

For local inspection:

```bash
python -m uvicorn issueweaver.api:app --reload --port 8000
```

Then open `http://127.0.0.1:8000/docs` for the Swagger interface or
`http://127.0.0.1:8000/health` for health status. The webhook endpoint is
`POST /webhook/github`; **unsigned requests must return 403**.

GitHub needs a publicly reachable **HTTPS** URL, such as a secured reverse
proxy or tunnel to port 8000. In the *playground repo only*, go to Settings ->
Webhooks -> Add webhook. Use `https://YOUR-HOST/webhook/github`, content type
`application/json`, the exact secret in `.env`, and subscribe to **Issues**.
Create label `swarm-ready` and add it to an issue to trigger processing.
The label is deliberate opt-in. Leave `GITHUB_ALLOW_PR=false` at first.

**Do not expose a local dev server with privileged Docker access to public traffic.**
For a real deployment use a dedicated locked-down worker, HTTPS, secret
management, a durable queue, and stronger VM isolation. Webhook processing
currently runs in a FastAPI background task, and delivery IDs/status are
persisted to SQLite; a crash does not automatically resume an in-flight task.

## 8. CI, maintenance, security and public release

Run `python -m pytest -q --cov=issueweaver` and `ruff check .` before commits.
GitHub Actions runs tests/lint on Python 3.11, 3.12, 3.13 and builds the
sandbox image. To change the repo from private to public **only after testing**,
open the NEW framework repo -> Settings -> General -> Danger Zone -> Change
repository visibility -> Public. First scan commits, `.env`, workflows, keys,
AI output, and GitHub settings. No automation performs this visibility change.

## 9. Troubleshooting

| Symptom | Action |
|---|---|
| `python: command not found` | Install Python 3.11+ and reopen terminal |
| Activation blocked | PowerShell process-level ExecutionPolicy Bypass, then activate |
| `ModuleNotFoundError: langgraph` | `python -m pip install -e '.[dev]'` in active venv |
| `DockerException` / daemon unavailable | Start Docker Desktop/Engine; run `docker version` |
| `ImageNotFound` | `docker build -t issueweaver-pytest:local sandbox/` |
| `pytest` import failure inside container | Build a reviewed custom runner with target dependencies |
| `401/403` GitHub | Check fine-grained token, repo selection, and token permissions |
| `403` webhook | Verify configured secret and raw request HMAC header |
| `tests_failed` | Inspect `runs/issue-N.json`; add meaningful tests or modify issue |
| `GITHUB_ALLOW_PR` rejection | Expected safeguard; set true only after dry-run |
| New repo name already taken | Pick a new name **in the script**; do not overwrite old repos |

## 10. Further study (authoritative references)

- LangGraph StateGraph: https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- GitHub webhook HMAC: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- GitHub Git trees: https://docs.github.com/en/rest/git/trees
- Docker security: https://docs.docker.com/engine/security/
- Pytest basics: https://docs.pytest.org/en/stable/getting-started.html
- FastAPI docs: https://fastapi.tiangolo.com/


## Windows Pytest startup error: WinError 10106

If the **demo** prints `import _overlapped` followed by `WinError 10106`,
Python's subprocess may have lost the Windows `SystemRoot` environment setting.
IssueWeaver's trusted demo runner now retains the necessary Windows runtime
variables and disables unrelated third-party Pytest plugins. It also treats
this startup failure as an infrastructure error instead of repeatedly asking
the Repair agent to change generated code.

From the project directory, with `.venv` active:

```powershell
python -c "import asyncio; print('asyncio works')"
python -m issueweaver demo
python -m pytest -q
```

If the **first** command fails outside the demo, the problem affects the
Windows Python environment itself; restarting the PC and checking installed
network/VPN software may be necessary. Do not reset Winsock or reinstall
Python just because the old demo runner produced this error.
