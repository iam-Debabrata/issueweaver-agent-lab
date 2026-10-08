#!/usr/bin/env bash
set -euo pipefail
# Run from the extracted IssueWeaver_Lab directory. Never affects existing repos.
REPOSITORY="iam-Debabrata/issueweaver-agent-lab"
command -v gh >/dev/null || { echo "Install GitHub CLI (gh) first."; exit 1; }
command -v git >/dev/null || { echo "Install Git first."; exit 1; }
gh auth status >/dev/null || { echo "Run: gh auth login"; exit 1; }
if gh repo view "$REPOSITORY" >/dev/null 2>&1; then
  echo "$REPOSITORY already exists; refusing to overwrite it."
  exit 1
fi
if [[ -d .git ]]; then
  echo "This directory already contains .git. Refusing to change its remote."
  exit 1
fi
git init -b main
git config user.name "$(gh api user --jq .login)"
git config user.email "$(gh api user --jq .id)+$(gh api user --jq .login)@users.noreply.github.com"
git add .
git commit -m "feat: initial IssueWeaver Lab framework"
gh repo create "$REPOSITORY" --private --source=. --remote=origin --push
printf '\nCreated PRIVATE GitHub repo: https://github.com/%s\n' "$REPOSITORY"
