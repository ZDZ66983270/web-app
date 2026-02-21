#!/bin/bash
# 强制刷新监控脚本 - 30秒倒计时

LOG_FILE="/Users/zhangzy/My Docs/Privates/22-AI编程/AI+风控App/web-app/backend/logs/backend.log"

echo "======================================================================"
echo "强制刷新监控 - 准备就绪"
echo "======================================================================"
echo ""
echo "监控日志文件: $LOG_FILE"
echo ""
echo "🕒 30秒倒计时开始,请在倒计时期间触发强制刷新..."
echo ""

# 30秒倒计时
for i in {30..1}; do
    echo -ne "\r⏰ 倒计时: $i 秒  "
    sleep 1
done

echo -e "\n"
echo "======================================================================"
echo "📊 开始监控强制刷新日志 (按Ctrl+C停止)"
echo "======================================================================"
echo ""

# 监控关键日志
tail -f "$LOG_FILE" | grep --line-buffered -E "(DataOrchestrator|强制刷新|决策|force-refresh|fetch_latest_data)"
