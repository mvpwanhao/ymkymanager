#!/usr/bin/env bash
# ????????? Docker??
# git pull -> (requirements.txt ??? pip install) -> systemctl restart ymky
#
# crontab ???
#   */5 * * * * /home/wanhao/ymky_manager/scripts/server_git_pull_deploy.sh >> /home/wanhao/ymky_manager/logs/pull.log 2>&1
#
# ???????
#   GIT_REMOTE=origin
#   DEPLOY_BRANCH=main
#   SERVICE_NAME=ymky
#   VENV_PATH=/home/wanhao/ymky_manager/.venv

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-ymky}"
VENV_PATH="${VENV_PATH:-$ROOT/.venv}"

before_req="$(sha1sum requirements.txt 2>/dev/null | awk '{print $1}' || true)"
git pull "$REMOTE" "$BRANCH"
after_req="$(sha1sum requirements.txt 2>/dev/null | awk '{print $1}' || true)"

if [[ "$before_req" != "$after_req" ]]; then
  "$VENV_PATH/bin/python" -m pip install -U pip
  "$VENV_PATH/bin/python" -m pip install -r requirements.txt
fi

sudo systemctl restart "$SERVICE_NAME"
echo "$(date -Is) pull+restart ok"
