#!/usr/bin/env bash
# 从运行中的 sakurafrp 容器 /run/config.json 读取 token 写入项目根 .env（不打印 token）
#   bash scripts/sync_natfrp_token_to_env.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! docker ps --format '{{.Names}}' | grep -qx 'sakurafrp'; then
  echo "error: 容器 sakurafrp 未运行" >&2
  exit 1
fi
if docker exec sakurafrp python3 -c True 2>/dev/null; then
  TOKEN="$(docker exec sakurafrp python3 -c 'import json; print(json.load(open("/run/config.json"))["token"])')"
else
  TOKEN="$(docker exec sakurafrp sed -n 's/.*\"token\": \"\(.*\)\".*/\1/p' /run/config.json)"
fi
[[ -n "$TOKEN" ]] || exit 1
touch .env
if grep -q '^NATFRP_TOKEN=' .env; then
  sed -i.bak "s|^NATFRP_TOKEN=.*|NATFRP_TOKEN=${TOKEN}|" .env && rm -f .env.bak
else
  printf '\nNATFRP_TOKEN=%s\n' "${TOKEN}" >>.env
fi
echo "ok: NATFRP_TOKEN written to .env (from sakurafrp container config)"
