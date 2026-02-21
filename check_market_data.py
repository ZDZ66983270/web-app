from sqlmodel import create_engine, Session, text

engine = create_engine('sqlite:///data/vera.db')

with Session(engine) as session:
    # 查看所有表
    tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
    print("📋 数据库表列表:")
    for table in tables:
        print(f"  - {table}")
    
    # 查看每个表的记录数
    print("\n📊 表记录统计:")
    for table in tables:
        try:
            count = session.exec(text(f"SELECT COUNT(*) FROM {table}")).first()
            print(f"  {table}: {count[0]} 条记录")
        except Exception as e:
            print(f"  {table}: 查询失败 - {e}")
    
    print("\n" + "="*80)
    
    # 查询最新数据统计
    result = session.exec(text("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as unique_symbols,
            MAX(timestamp) as latest_date
        FROM marketdatadaily
    """)).first()
    
    print(f"\n📊 行情数据统计:")
    print(f"  总记录数: {result[0]}")
    print(f"  资产数量: {result[1]}")
    print(f"  最新日期: {result[2]}")
    
    # 查询最新一天的估值数据
    print("\n" + "="*80)
    print(f"\n💰 最新估值数据样本 (PE/PB/PS):")
    print(f"{'Symbol':<20} {'Date':<12} {'Close':>10} {'PE':>8} {'PB':>8} {'PS':>8}")
    print("-" * 80)
    
    latest_data = session.exec(text("""
        SELECT symbol, timestamp, close, pe_ratio, pb_ratio, ps_ratio
        FROM marketdatadaily
        WHERE timestamp = (SELECT MAX(timestamp) FROM marketdatadaily)
        AND (pe_ratio IS NOT NULL OR pb_ratio IS NOT NULL OR ps_ratio IS NOT NULL)
        ORDER BY symbol
        LIMIT 20
    """)).all()
    
    for row in latest_data:
        symbol, date, close, pe, pb, ps = row
        pe_str = f"{pe:.2f}" if pe else "N/A"
        pb_str = f"{pb:.2f}" if pb else "N/A"
        ps_str = f"{ps:.2f}" if ps else "N/A"
        print(f"{symbol:<20} {date:<12} {close:>10.2f} {pe_str:>8} {pb_str:>8} {ps_str:>8}")
    
    # 统计有估值数据的资产
    print("\n" + "="*80)
    valuation_stats = session.exec(text("""
        SELECT 
            COUNT(DISTINCT symbol) as symbols_with_pe,
            (SELECT COUNT(DISTINCT symbol) FROM marketdatadaily WHERE pb_ratio IS NOT NULL AND timestamp = (SELECT MAX(timestamp) FROM marketdatadaily)) as symbols_with_pb,
            (SELECT COUNT(DISTINCT symbol) FROM marketdatadaily WHERE ps_ratio IS NOT NULL AND timestamp = (SELECT MAX(timestamp) FROM marketdatadaily)) as symbols_with_ps
        FROM marketdatadaily
        WHERE pe_ratio IS NOT NULL 
        AND timestamp = (SELECT MAX(timestamp) FROM marketdatadaily)
    """)).first()
    
    print(f"\n📈 估值数据覆盖率 (最新日期):")
    print(f"  有 PE 数据: {valuation_stats[0]} 个资产")
    print(f"  有 PB 数据: {valuation_stats[1]} 个资产")
    print(f"  有 PS 数据: {valuation_stats[2]} 个资产")
