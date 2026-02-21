#!/usr/bin/env python3
"""
检查财务数据库中的财报记录，特别关注 report_type 和重复日期问题
"""
import sys
sys.path.append('backend')
from sqlmodel import Session, select
from backend.database import engine
from backend.models import FinancialFundamentals
import pandas as pd

def check_financials(symbol):
    print(f"\n{'='*80}")
    print(f"检查 {symbol} 的财报数据")
    print(f"{'='*80}\n")
    
    with Session(engine) as session:
        fins = session.exec(
            select(FinancialFundamentals)
            .where(FinancialFundamentals.symbol == symbol)
            .order_by(FinancialFundamentals.as_of_date.desc())
        ).all()
        
        if not fins:
            print(f"❌ 没有找到 {symbol} 的财报数据")
            return
        
        print(f"找到 {len(fins)} 条财报记录:\n")
        
        data = []
        for f in fins:
            data.append({
                '日期': f.as_of_date,
                '类型': f.report_type,
                '净利润(亿)': f"{f.net_income_ttm/1e9:.2f}" if f.net_income_ttm else "N/A",
                'EPS': f"{f.eps:.2f}" if f.eps else "N/A",
                '数据源': f.data_source,
                '币种': f.currency
            })
        
        df = pd.DataFrame(data)
        print(df.to_string(index=False))
        
        # 检查重复日期
        dates = [f.as_of_date for f in fins]
        duplicates = [d for d in dates if dates.count(d) > 1]
        if duplicates:
            print(f"\n⚠️  发现重复日期: {set(duplicates)}")
            for dup_date in set(duplicates):
                print(f"\n  {dup_date} 的记录:")
                dup_records = [f for f in fins if f.as_of_date == dup_date]
                for r in dup_records:
                    print(f"    - 类型: {r.report_type}, 净利润: {r.net_income_ttm/1e9:.2f}亿, EPS: {r.eps}, 来源: {r.data_source}")
        
        # 检查季度数据
        quarterly = [f for f in fins if f.report_type == 'quarterly']
        if quarterly:
            print(f"\n📊 季度数据 (最近4个季度):")
            for q in quarterly[:4]:
                print(f"  {q.as_of_date}: 净利润 {q.net_income_ttm/1e9:.2f}亿, EPS {q.eps}")
            
            if len(quarterly) >= 4:
                ttm_income = sum(q.net_income_ttm for q in quarterly[:4] if q.net_income_ttm)
                ttm_eps = sum(q.eps for q in quarterly[:4] if q.eps)
                print(f"\n  ✅ TTM 净利润 (4季度总和): {ttm_income/1e9:.2f}亿")
                print(f"  ✅ TTM EPS (4季度总和): {ttm_eps:.2f}")

if __name__ == "__main__":
    check_financials("US:STOCK:MSFT")
    check_financials("US:STOCK:TSLA")
    check_financials("US:STOCK:AAPL")
    check_financials("HK:STOCK:00700")
    check_financials("CN:STOCK:600030")
