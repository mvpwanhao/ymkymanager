#!/usr/bin/env bash
# ── 备份验证脚本 ──────────────────────────
# 用法：./scripts/db_verify_backup.sh <backup_file.sql.gz>
# 如果不传参数，则验证最近一次备份
#
# 验证内容：
#   1. 文件存在且非空
#   2. gzip 完整性
#   3. SQL 内容包含预期表名
#   4. 解压后行数统计

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${ROOT}/backups"
LOG_FILE="${ROOT}/logs/db_backup.log"

if [ $# -ge 1 ]; then
    BACKUP_FILE="$1"
else
    # 自动选取最近的备份
    BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/ymky_db_*.sql.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        echo "ERROR: 未找到备份文件"
        exit 1
    fi
    echo "自动选取最近备份: ${BACKUP_FILE}"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: 文件不存在: ${BACKUP_FILE}"
    exit 1
fi

EXIT_CODE=0

# 1) 文件大小
FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
ACTUAL_BYTES="$(stat -c %s "$BACKUP_FILE" 2>/dev/null || stat -f %z "$BACKUP_FILE" 2>/dev/null || echo 0)"
echo "文件大小: ${FILE_SIZE} (${ACTUAL_BYTES} bytes)"

if [ "$ACTUAL_BYTES" -lt 100 ]; then
    echo "FAIL: 文件过小，可能为空"
    exit 1
fi
echo "OK: 文件大小检查通过"

# 2) gzip 完整性
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "OK: gzip 完整性检查通过"
else
    echo "FAIL: gzip 文件损坏"
    exit 1
fi

# 3) SQL 内容验证
TABLE_HITS=$(zcat "$BACKUP_FILE" 2>/dev/null | grep -c -E "CREATE TABLE|COPY.*(actual_production|energy_reporting|actual_sales)" || true)
if [ "$TABLE_HITS" -lt 1 ]; then
    echo "WARN: 未检测到预期表名"
    EXIT_CODE=1
else
    echo "OK: 检测到 ${TABLE_HITS} 处表定义/数据引用"
fi

# 4) 解压后行数
LINE_COUNT=$(zcat "$BACKUP_FILE" 2>/dev/null | wc -l || echo 0)
echo "解压后总行数: ${LINE_COUNT}"

if [ "$LINE_COUNT" -lt 50 ]; then
    echo "WARN: SQL 内容过少（${LINE_COUNT} 行），可能不完整"
    EXIT_CODE=1
else
    echo "OK: SQL 行数检查通过"
fi

# 5) 列出备份中包含的表名
echo ""
echo "备份中包含的表:"
zcat "$BACKUP_FILE" 2>/dev/null | grep -oE "CREATE TABLE [^\"]*\"[^\"]+\"" | sed 's/CREATE TABLE.*"\(.*\)"/  - \1/' || echo "  （未检测到 CREATE TABLE 语句）"

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "=== 验证通过 ==="
else
    echo "=== 验证有警告，请人工检查 ==="
fi

exit $EXIT_CODE
