#!/usr/bin/env bash
# Docker 部署：git pull ->（源码/镜像上下文变化则 build）compose up -d
#
# Cron 示例（Docker 模式下替代 server_git_pull_deploy.sh）：
#   */5 * * * * /home/wanhao/ymky_manager/scripts/server_git_pull_deploy_docker.sh >> /home/wanhao/ymky_manager/logs/pull.log 2>&1
#
# 要求运行用户对 docker.sock 有权访问（在 docker 组内）；勿再 systemctl restart ymky。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "$(date -Is) error: Docker daemon 不可用。请登录到 docker 组或执行 newgrp docker" >&2
  exit 1
fi

REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"

needs_compose_build() {
  git diff --name-only "$1".."$2" 2>/dev/null | grep -qE \
    '^(Dockerfile|docker-compose\.yml|requirements\.txt|VERSION|app/|templates/|static/|docker/)' \
    || false
}

before_head="$(git rev-parse HEAD)"

git pull "$REMOTE" "$BRANCH"

after_head="$(git rev-parse HEAD)"

if [[ "$before_head" != "$after_head" ]] && needs_compose_build "$before_head" "$after_head"; then
  docker compose build
fi

docker compose up -d

echo "$(date -Is) docker pull+up ok"
