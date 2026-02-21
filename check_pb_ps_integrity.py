
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def check_pb_ps_integrity():
    db_path = 'backend/database.db'
    conn = sqlite3.connect(db_path)
    
    # 获取最近 7 天的数据
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    query = """
    SELECT symbol, market, timestamp, close, pe, pe_ttm, pb, ps, dividend_yield
    FROM marketdatadaily
    WHERE timestamp >= ?
    ORDER BY timestamp DESC, symbol ASC
    """
    
    df = pd.read_sql_query(query, conn, params=(seven_days_ago,))
    conn.close()
    
    if df.empty:
        print("❌ 未找到最近 7 天的行情数据。")
        return

    print(f"📊 最近 7 天行情数据汇总 (共 {len(df)} 条记录):")
    
    # 检查 PB/PS 缺失情况
    missing_pb = df[df['pb'].isna() | (df['pb'] == 0)]
    missing_ps = df[df['ps'].isna() | (df['ps'] == 0)]
    
    print(f"\n📈 PB 缺失率: {len(missing_pb)}/{len(df)} ({len(missing_pb)/len(df)*100:.1f}%)")
    print(f"📈 PS 缺失率: {len(missing_ps)}/{len(df)} ({len(missing_ps)/len(df)*100:.1f}%)")
    
    # 显示部分样本
    print("\n📝 数据样本 (最新):")
    # 只看前 20 条，包含常见股票
    sample_symbols = ['CN:STOCK:600036', 'HK:STOCK:00700', 'CN:STOCK:600536', 'HK:STOCK:03968']
    mask = df['symbol'].isin(sample_symbols)
    if mask.any():
        print(df[mask].head(20).to_string(index=False))
    else:
        print(df.head(20).to_string(index=False))

    # 检查是否有 PB/PS 为 0 或 None 的情况（针对刚才更新过的股票）
    print("\n🔍 检查最近更新的重点标的:")
    for sym in sample_symbols:
        sym_data = df[df['symbol'] == sym]
        if not sym_data.empty:
            latest = sym_data.iloc[0]
            status = "✅ 完整" if pd.notna(latest['pb']) and pd.notna(latest['ps']) and latest['pb'] != 0 and latest['ps'] != 0 else "❌ 缺失"
            print(f"  - {sym}: PB={latest['pb']}, PS={latest['ps']} -> {status}")

if __name__ == "__main__":
    check_pb_ps_integrity()
