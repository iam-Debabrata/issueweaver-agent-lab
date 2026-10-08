$ErrorActionPreference = 'Stop'
# Run from the extracted IssueWeaver_Lab directory. Never changes existing repositories.
$repo = 'iam-Debabrata/issueweaver-agent-lab'
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI (gh) first.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git first.' }
gh auth status 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login first.' }
gh repo view $repo 2>$null
if ($LASTEXITCODE -eq 0) { throw "Repository $repo already exists; refusing to overwrite." }
if (Test-Path .git) { throw 'This folder already has .git; refusing to alter a remote.' }
git init -b main
$user = gh api user --jq .login
$id = gh api user --jq .id
git config user.name $user
git config user.email "$id+$user@users.noreply.github.com"
git add .
git commit -m 'feat: initial IssueWeaver Lab framework'
gh repo create $repo --private --source=. --remote=origin --push
if ($LASTEXITCODE -ne 0) { throw 'GitHub repository creation/push failed.' }
Write-Output "Created PRIVATE GitHub repo: https://github.com/$repo"
