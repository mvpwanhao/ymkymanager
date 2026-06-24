#!/usr/bin/env bash
# ── 服务健康检查告警脚本 ──────────────────────────────
# 用于生产服务器，由 cron 定期执行（建议每 5 分钟）。
# 若 /health 返回非 200 或超时，则通过 Server酱 推送告警到微信。
#
# 安装到 cron（以 <user> 用户）：
#   crontab -e
#   */5 * * * * /home/<user>/ymky_manager/scripts/health_check_alert.sh >> /home/<user>/ymky_manager/logs/health.log 2>&1
#
# 依赖：curl（通常已安装）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

HEALTH_URL="http://127.0.0.1:8080/health"
TIMEOUT_SEC=10
LOG_FILE="logs/health.log"

# 从 .env 中读取 SERVERCHAN_SENDKEY（优先），否则从环境变量读取
SENDKEY=""
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    SENDKEY="$(grep -E "^SERVERCHAN_SENDKEY=" "$ENV_FILE" | head -1 | cut -d= -f2- | xargs)"
fi
if [ -z "$SENDKEY" ]; then
    SENDKEY="${SERVERCHAN_SENDKEY:-}"
fi

echo "$(date -Is) health check start" >> "$LOG_FILE"

# 执行健康检查
HTTP_CODE=""
RESP_BODY=""
if command -v curl &>/dev/null; then
    RESP=$(curl -s -o /tmp/ymky_health_resp.json -w "%{http_code}" --max-time "$TIMEOUT_SEC" "$HEALTH_URL" 2>/dev/null || true)
    HTTP_CODE="$RESP"
    if [ -f /tmp/ymky_health_resp.json ]; then
        RESP_BODY=$(cat /tmp/ymky_health_resp.json 2>/dev/null || true)
    fi
else
    echo "$(date -Is) ERROR: curl not found" >> "$LOG_FILE"
    exit 1
fi

if [ "$HTTP_CODE" = "200" ]; then
    # 健康 — 如果上次失败则发送恢复通知（可选：仅打印日志不发送微信）
    echo "$(date -Is) OK (HTTP 200)" >> "$LOG_FILE"
    exit 0
fi

# ── 非 200 → 发送告警 ──
echo "$(date -Is) ALERT: HTTP $HTTP_CODE" >> "$LOG_FILE"

if [ -z "$SENDKEY" ]; then
    echo "$(date -Is) WARN: SERVERCHAN_SENDKEY 未配置，跳过微信告警" >> "$LOG_FILE"
    exit 0
fi

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
TITLE="🚨 【CRITICAL】YMKY 服务异常"
DESP="📌 健康检查失败（HTTP ${HTTP_CODE}）
🕐 ${TIMESTAMP}

📋 详情：
- 检查地址：${HEALTH_URL}
- HTTP 状态码：${HTTP_CODE}
- 响应体：${RESP_BODY:-(空)}"

# 通过 Server酱 发送
API_URL="https://sctapi.ftqq.com/${SENDKEY}.send"
curl -s -X POST "$API_URL" \
    --data-urlencode "title=${TITLE}" \
    --data-urlencode "desp=${DESP}" \
    --max-time 10 \
    >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "$(date -Is) alert sent" >> "$LOG_FILE"
