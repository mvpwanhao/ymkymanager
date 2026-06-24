#!/usr/bin/env bash
# rsync ?????????? Docker?????? pull+restart ???
# ?????? rsync ?? ssh ?????
#
# ???
#   export DEPLOY_SSH=<user>@<server-ip>
#   export DEPLOY_PATH=/home/<user>/ymky_manager
#   chmod +x scripts/deploy_via_rsync.sh
#   ./scripts/deploy_via_rsync.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_SSH="${DEPLOY_SSH:-<user>@<server-ip>}"
DEPLOY_PATH="${DEPLOY_PATH:-/home/<user>/ymky_manager}"

echo "Sync from: $ROOT"
echo "Target:    $DEPLOY_SSH:$DEPLOY_PATH"

rsync -avz \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'data/' \
  --exclude 'database_backup/' \
  --exclude '.cursor/' \
  --exclude '.idea/' \
  --exclude '.vscode/' \
  "$ROOT/" "$DEPLOY_SSH:$DEPLOY_PATH/"

echo "Remote pull+restart..."
ssh "$DEPLOY_SSH" "set -e; cd $DEPLOY_PATH && chmod +x ./scripts/server_git_pull_deploy.sh && ./scripts/server_git_pull_deploy.sh"

echo "Done."
