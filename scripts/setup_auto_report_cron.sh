#!/bin/bash
# ===================================================================
# 自动报表 cron 定时任务安装脚本
#
# 在宿主机上运行此脚本，会自动添加 cron 任务：
#   8:30-8:55 每 5 分钟执行一次 auto_report.py
#
# 用法:
#   bash scripts/setup_auto_report_cron.sh
#
# 卸载:
#   crontab -l | grep -v auto_report | crontab -
# ===================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="ymky-manager"
LOG_FILE="${PROJECT_DIR}/data/auto_report.log"
PYTHON_BIN="python"

echo "项目目录: ${PROJECT_DIR}"
echo "容器名:   ${CONTAINER}"
echo "日志文件: ${LOG_FILE}"
echo ""

# 检查 docker 命令
if ! command -v docker &>/dev/null; then
    echo "错误: 未找到 docker 命令"
    exit 1
fi

# 检查容器是否运行
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
    echo "警告: 容器 ${CONTAINER} 当前未运行（cron 任务仍会安装，容器启动后生效）"
fi

# 构造 cron 命令
CMD="cd ${PROJECT_DIR} && docker exec ${CONTAINER} ${PYTHON_BIN} scripts/auto_report.py >> ${LOG_FILE} 2>&1"

# 生成 cron 条目
read -r -d '' CRON_ENTRIES << EOF || true
# ---- auto_report: 8:30-8:55 每5分钟 ----
30,35,40,45,50,55 8 * * * ${CMD}
EOF

# 移除旧的同名任务，追加新任务
(crontab -l 2>/dev/null | grep -v "auto_report" || true; echo "${CRON_ENTRIES}") | crontab -

echo "========================================"
echo "cron 定时任务已安装:"
echo "========================================"
echo "${CRON_ENTRIES}"
echo "========================================"
echo ""
echo "查看当前 crontab:  crontab -l"
echo "查看运行日志:      tail -f ${LOG_FILE}"
echo "手动测试一次:      docker exec ${CONTAINER} ${PYTHON_BIN} scripts/auto_report.py"
echo "卸载定时任务:      crontab -l | grep -v auto_report | crontab -"
