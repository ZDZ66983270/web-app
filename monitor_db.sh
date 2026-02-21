#!/bin/bash
# 实时监控数据库表的变化

echo "======================================================================"
echo "数据库实时监控"
echo "======================================================================"
echo ""

while true; do
    clear
    echo "======================================================================"
    echo "数据库状态监控 - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================================================"
    echo ""
    
    # 表记录数统计
    echo "📊 表记录数统计:"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT 
        'Watchlist' as table_name, 
        COUNT(*) as count 
    FROM watchlist 
    UNION ALL 
    SELECT 'Index', COUNT(*) FROM 'index'
    UNION ALL 
    SELECT 'RawMarketData', COUNT(*) FROM rawmarketdata 
    UNION ALL 
    SELECT 'MarketDataDaily', COUNT(*) FROM marketdatadaily 
    UNION ALL 
    SELECT 'MarketSnapshot', COUNT(*) FROM marketsnapshot
    " | column -t -s '|'
    
    echo ""
    echo "📋 Watchlist (自选股):"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT symbol, market, name, added_at 
    FROM watchlist 
    ORDER BY added_at DESC
    " | column -t -s '|' | head -10
    
    echo ""
    echo "📊 Index (指数配置):"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT symbol, market, name 
    FROM 'index' 
    ORDER BY market, symbol
    " | column -t -s '|'
    
    echo ""
    echo "📦 最新 RawMarketData (原始数据):"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT 
        symbol, 
        market, 
        source,
        processed,
        substr(fetch_time, 1, 19) as fetch_time
    FROM rawmarketdata 
    ORDER BY id DESC 
    LIMIT 5
    " | column -t -s '|'
    
    echo ""
    echo "📸 MarketSnapshot (快照数据) - 按市场分组:"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT 
        market,
        COUNT(*) as count,
        GROUP_CONCAT(symbol, ', ') as symbols
    FROM marketsnapshot 
    GROUP BY market
    ORDER BY market
    " | column -t -s '|'
    
    echo ""
    echo "📈 MarketDataDaily (历史数据) - 按股票统计:"
    echo "----------------------------------------------------------------------"
    sqlite3 backend/database.db "
    SELECT 
        symbol,
        market,
        COUNT(*) as records,
        MIN(substr(timestamp, 1, 10)) as earliest,
        MAX(substr(timestamp, 1, 10)) as latest
    FROM marketdatadaily 
    GROUP BY symbol, market
    ORDER BY market, symbol
    " | column -t -s '|'
    
    echo ""
    echo "======================================================================"
    echo "按 Ctrl+C 停止监控 | 每5秒刷新一次"
    echo "======================================================================"
    
    sleep 5
done
