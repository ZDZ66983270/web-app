#!/bin/bash
# 每日增量更新 - Cron配置脚本
# 自动设置cron定时任务

APP_DIR="/Users/zhangzy/My Docs/Privates/22-AI编程/AI+风控App/web-app"
SCRIPT="$APP_DIR/daily_incremental_update.py"
LOG_FILE="/tmp/daily_market_update.log"
ERROR_LOG="/tmp/daily_market_update_error.log"

# Cron任务配置（每天18:00执行）
CRON_JOB="0 18 * * * cd \"$APP_DIR\" && /usr/bin/python3 daily_incremental_update.py >> $LOG_FILE 2>> $ERROR_LOG"

echo "=== 每日增量更新 - Cron定时任务配置 ==="
echo ""
echo "将添加以下Cron任务："
echo "$CRON_JOB"
echo ""
echo "执行时间：每天18:00"
echo "日志文件：$LOG_FILE"
echo "错误日志：$ERROR_LOG"
echo ""
read -p "确认添加？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # 备份现有crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null
    
    # 添加新任务
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    
    echo "✅ Cron任务已添加"
    echo ""
    echo "验证："
    crontab -l | grep "daily_incremental_update"
    echo ""
    echo "查看日志："
    echo "  tail -f $LOG_FILE"
else
    echo "❌ 已取消"
fi
