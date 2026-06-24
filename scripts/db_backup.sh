#!/usr/bin/env bash
# ── Supabase PostgreSQL 自动备份脚本 ──────────────────
# 用法：./scripts/db_backup.sh
# 建议 cron：每天凌晨 4:00 执行
#   0 4 * * * /home/<user>/ymky_manager/scripts/db_backup.sh >> /home/<user>/ymky_manager/logs/db_backup.log 2>&1
#
# 备份策略：
#   - 完整 SQL 备份（pg_dump），保留最近 7 天
#   - 每周日额外保留一份周备份（保留 4 周）
#   - 备份文件加密？否（服务器内安全，如需加密可后续添加）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p backups logs
LOG_FILE="logs/db_backup.log"
BACKUP_DIR="backups"

echo "$(date -Is) === 数据库备份开始 ===" >> "$LOG_FILE"

# 从 .env 读取 DATABASE_URL
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "$(date -Is) ERROR: .env 文件不存在，无法获取数据库连接信息" >> "$LOG_FILE"
    exit 1
fi

DATABASE_URL="$(grep -E "^DATABASE_URL=" "$ENV_FILE" | head -1 | cut -d= -f2- | xargs)"
if [ -z "$DATABASE_URL" ]; then
    echo "$(date -Is) ERROR: DATABASE_URL 未配置" >> "$LOG_FILE"
    exit 1
fi

# 解析 DATABASE_URL 为 pg_dump 参数
# 格式：postgresql+psycopg2://user:pass@host:port/dbname?sslmode=require
RAW_URL="${DATABASE_URL#*://}"            # 去掉 postgresql+psycopg2://
USER_PASS="${RAW_URL%%@*}"                # user:pass
HOST_DB="${RAW_URL#*@}"                   # host:port/dbname?params
DB_USER="${USER_PASS%%:*}"
DB_PASS="${USER_PASS#*:}"
HOST="${HOST_DB%%:*}"
HOST_PORT="${HOST_DB%%/*}"
DB_NAME="${HOST_DB#*/}"
DB_NAME="${DB_NAME%%\?*}"                 # 去掉查询参数

# 导出密码环境变量供 pg_dump 使用
# URL??????? %40 ????
DB_PASS_DECODED=$(python3 -c "import sys,urllib.parse; sys.stdout.write(urllib.parse.unquote(sys.argv[1]))" "$DB_PASS" 2>/dev/null || echo "$DB_PASS")
export PGPASSWORD="$DB_PASS_DECODED"

DATE_TAG="$(date +%Y%m%d)"
BACKUP_FILE="${BACKUP_DIR}/ymky_db_${DATE_TAG}.sql.gz"
WEEKDAY="$(date +%u)"  # 1=周一, 7=周日

echo "$(date -Is) 备份到: ${BACKUP_FILE}" >> "$LOG_FILE"

# 执行备份
if pg_dump -h "$HOST" -p 6543 -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl | gzip > "$BACKUP_FILE"; then
    FILE_SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
    echo "$(date -Is) OK: 备份完成，大小 ${FILE_SIZE}" >> "$LOG_FILE"
else
    echo "$(date -Is) ERROR: pg_dump 执行失败" >> "$LOG_FILE"
    exit 1
fi

# ── 清理旧备份 ─────────────────────────
# 保留最近 7 天的日备份
find "$BACKUP_DIR" -name "ymky_db_*.sql.gz" -mtime +7 -not -name "*_weekly*" -delete 2>/dev/null || true

# 周日额外保留一份周备份
if [ "$WEEKDAY" = "7" ]; then
    WEEKLY_FILE="${BACKUP_DIR}/ymky_db_weekly_${DATE_TAG}.sql.gz"
    cp "$BACKUP_FILE" "$WEEKLY_FILE"
    echo "$(date -Is) 周备份已保留: ${WEEKLY_FILE}" >> "$LOG_FILE"
    # 保留最近 4 周的周备份
    find "$BACKUP_DIR" -name "ymky_db_weekly_*.sql.gz" -mtime +28 -delete 2>/dev/null || true
fi

# 列出当前备份
echo "$(date -Is) 当前备份文件:" >> "$LOG_FILE"
ls -lh "${BACKUP_DIR}"/ymky_db_*.sql.gz 2>/dev/null >> "$LOG_FILE" || echo "（无）" >> "$LOG_FILE"

echo "$(date -Is) === 数据库备份完成 ===" >> "$LOG_FILE"
