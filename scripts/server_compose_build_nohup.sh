#!/usr/bin/env bash
# 在无交互 SSH 会话中后台完成 compose build/up；日志写入 /tmp/ymky-docker-build.log
#
#   nohup bash scripts/server_compose_build_nohup.sh >/dev/null 2>&1 &
#   tail -f /tmp/ymky-docker-build.log

set -euo pipefail
LOG=/tmp/ymky-docker-build.log
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

exec >>"$LOG" 2>&1
echo "--- $(date -Is) rebuild start ROOT=$ROOT"

dc() {
  if docker info >/dev/null 2>&1; then docker compose "$@"; elif sg docker -c 'docker info' >/dev/null 2>&1; then
    local q
    q=$(printf '%q ' "$@")
    sg docker -c "cd $(printf '%q' "$ROOT") && docker compose ${q% }"
  else
    echo "No docker/socket access"; exit 1
  fi
}

cd "$ROOT"
dc build
dc up -d
dc ps
curl -sS http://127.0.0.1:8080/health || true
echo "--- $(date -Is) rebuild done"
