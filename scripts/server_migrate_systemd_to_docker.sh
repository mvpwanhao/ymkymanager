#!/usr/bin/env bash
# 在无 Docker 的 systemd + venv 部署上，切换到 docker compose。
# 先在同一台机上执行（一次）: sudo bash scripts/server_install_docker_ubuntu.sh
#
# 然后以普通用户在项目根运行:
#   bash scripts/server_migrate_systemd_to_docker.sh
#
# 会: stop/disable ymky、git pull（可选跳过）、compose up；
# cron 请将 server_git_pull_deploy.sh 换成 server_git_pull_deploy_docker.sh。
#
# Env:
#   SKIP_GIT_PULL=1   — 不做 git pull（例如离线或已手动同步）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${SKIP_SYSTEMD_STOP:-}" != "1" ]]; then
  if systemctl is-active --quiet ymky 2>/dev/null || systemctl is-enabled --quiet ymky 2>/dev/null; then
    echo "Stopping and disabling systemd unit ymky (need sudo for stop/disable) ..."
    sudo systemctl stop ymky || true
    sudo systemctl disable ymky || true
  fi
fi

dc() {
  if docker info >/dev/null 2>&1; then
    docker compose "$@"
  else
    local q
    q=$(printf '%q ' "$@")
    sg docker -c "cd $(printf '%q' "$ROOT") && docker compose ${q% }"
  fi
}

if ! docker info >/dev/null 2>&1 && ! sg docker -c 'docker info' >/dev/null 2>&1; then
  echo "无法访问 Docker daemon。请先: sudo bash $ROOT/scripts/server_install_docker_ubuntu.sh"
  echo "然后重试本脚本；若仍失败，执行: newgrp docker  或重新登录 SSH。"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "缺少 .env。请先: cp .env.example .env 并填写至少 YMKY_SECRET_KEY。"
  exit 1
fi

mkdir -p data logs

if [[ "${SKIP_GIT_PULL:-}" != "1" ]]; then
  git pull "${GIT_REMOTE:-origin}" "${DEPLOY_BRANCH:-main}" || true
fi

dc build
dc up -d

dc ps

echo "---"
echo "$(date -Is) docker compose up ok"
echo "健康检查: curl -s http://127.0.0.1:8080/health"
