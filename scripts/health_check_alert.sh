#!/usr/bin/env bash
# ── 服务健康检查告警脚本 ──────────────────────────────
# 用于生产服务器，由 cron 定期执行（建议每 5 分钟）。
# 若 /health 返回非 200 或超时，则推送告警到微信。
# 优先走自建推送服务器（WECHAT_PUSH_API_URL/TOKEN），未配置时回退 Server酱（SERVERCHAN_SENDKEY）。
#
# 安装到 cron（以 <user> 用户）：
#   crontab -e
#   */5 * * * * /home/<user>/ymky_manager/scripts/health_check_alert.sh >> /home/<user>/ymky_manager/logs/health.log 2>&1
#
# 依赖：curl、python3（构建 JSON 用）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

HEALTH_URL="http://127.0.0.1:8080/health"
TIMEOUT_SEC=10
LOG_FILE="logs/health.log"

# 从 .env 读取（优先），否则从环境变量读取
PUSH_URL=""
PUSH_TOKEN=""
SENDKEY=""
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    PUSH_URL="$(grep -E "^WECHAT_PUSH_API_URL=" "$ENV_FILE" | head -1 | cut -d= -f2- | xargs)"
    PUSH_TOKEN="$(grep -E "^WECHAT_PUSH_API_TOKEN=" "$ENV_FILE" | head -1 | cut -d= -f2- | xargs)"
    SENDKEY="$(grep -E "^SERVERCHAN_SENDKEY=" "$ENV_FILE" | head -1 | cut -d= -f2- | xargs)"
fi
[ -z "$PUSH_URL" ] && PUSH_URL="${WECHAT_PUSH_API_URL:-}"
[ -z "$PUSH_TOKEN" ] && PUSH_TOKEN="${WECHAT_PUSH_API_TOKEN:-}"
[ -z "$SENDKEY" ] && SENDKEY="${SERVERCHAN_SENDKEY:-}"

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
    # 健康 — 仅记录日志
    echo "$(date -Is) OK (HTTP 200)" >> "$LOG_FILE"
    exit 0
fi

# ── 非 200 → 发送告警 ──
echo "$(date -Is) ALERT: HTTP $HTTP_CODE" >> "$LOG_FILE"

if [ -z "$PUSH_URL" ] && [ -z "$SENDKEY" ]; then
    echo "$(date -Is) WARN: 未配置 WECHAT_PUSH_API_* 或 SERVERCHAN_SENDKEY，跳过微信告警" >> "$LOG_FILE"
    exit 0
fi

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
TITLE="🚨 【CRITICAL】YMKY 服务异常"
CONTENT="📌 健康检查失败（HTTP ${HTTP_CODE}）
🕐 ${TIMESTAMP}

📋 详情：
- 检查地址：${HEALTH_URL}
- HTTP 状态码：${HTTP_CODE}
- 响应体：${RESP_BODY:-(空)}"

if [ -n "$PUSH_URL" ] && [ -n "$PUSH_TOKEN" ]; then
    # 自建微信推送服务器（微信测试号模板消息）
    if command -v python3 &>/dev/null; then
        JSON_FILE="$(mktemp)"
        python3 -c 'import json,sys; json.dump({"title": sys.argv[1], "content": sys.argv[2]}, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)' "$TITLE" "$CONTENT" "$JSON_FILE"
        curl -s -X POST "$PUSH_URL" \
            -H "Authorization: Bearer $PUSH_TOKEN" \
            -H "Content-Type: application/json" \
            --data @"$JSON_FILE" \
            --max-time 10 \
            >> "$LOG_FILE" 2>&1
        rm -f "$JSON_FILE"
    else
        echo "$(date -Is) WARN: python3 不存在，无法发送自建推送" >> "$LOG_FILE"
    fi
elif [ -n "$SENDKEY" ]; then
    # 回退：Server酱
    API_URL="https://sctapi.ftqq.com/${SENDKEY}.send"
    curl -s -X POST "$API_URL" \
        --data-urlencode "title=${TITLE}" \
        --data-urlencode "desp=${CONTENT}" \
        --max-time 10 \
        >> "$LOG_FILE" 2>&1
fi

echo "" >> "$LOG_FILE"
echo "$(date -Is) alert sent" >> "$LOG_FILE"