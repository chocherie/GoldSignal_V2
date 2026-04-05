#!/usr/bin/env bash
# Create GoldSignal_V2 on GitHub (your account) and push local main.
#
# Prerequisites:
#   1. GitHub → Settings → Developer settings → Personal access tokens
#      Classic token with "repo" scope (or fine-grained: contents read/write).
#   2. export GITHUB_TOKEN="ghp_...."   # do not commit or paste into chat
#
# Usage:
#   ./scripts/create_github_repo_and_push.sh YOUR_GITHUB_USERNAME
#   ./scripts/create_github_repo_and_push.sh YOUR_GITHUB_USERNAME MyRepoName
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GITHUB_USER="${1:?Usage: $0 <github_username> [repo_name]}"
REPO_NAME="${2:-GoldSignal_V2}"
TOKEN="${GITHUB_TOKEN:?Set GITHUB_TOKEN (see header comment in this script)}"

echo "Creating repo ${GITHUB_USER}/${REPO_NAME} via GitHub API..."
HTTP_CODE="$(curl -sS -o /tmp/goldsignal_gh_create.json -w "%{http_code}" -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/user/repos" \
  -d "{\"name\":\"${REPO_NAME}\",\"private\":false,\"description\":\"Gold signal desk V2 — Bloomberg/GPR pipeline, FastAPI, React\"}")"

if [[ "$HTTP_CODE" == "201" ]]; then
  echo "Created https://github.com/${GITHUB_USER}/${REPO_NAME}"
elif [[ "$HTTP_CODE" == "422" ]]; then
  echo "GitHub returned 422 (repo may already exist). Body:"
  cat /tmp/goldsignal_gh_create.json
  echo ""
  echo "If the repo already exists, we will still try to push."
else
  echo "GitHub API error HTTP ${HTTP_CODE}:"
  cat /tmp/goldsignal_gh_create.json
  exit 1
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo "Pushing main..."
# x-access-token + PAT avoids interactive prompt for HTTPS
git push "https://x-access-token:${TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git" HEAD:main
git branch --set-upstream-to=origin/main main

echo ""
echo "Done. Open https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo "Remote: origin -> https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
