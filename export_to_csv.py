
import sys
import os
import pandas as pd
from sqlmodel import Session, select
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import engine
from models import MarketDataDaily, FinancialFundamentals, FINANCIAL_EXPORT_COLUMNS

def main():
    print("\n--- [步骤]: 导出标准化 CSV 数据 ---")
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    with Session(engine) as session:
        try:
            # 1. 导出财报历史 (使用 55 列标准排序)
            print("正在导出 financial_history.csv (55列标准排序)...")
            fins = session.exec(select(FinancialFundamentals).order_by(FinancialFundamentals.symbol, FinancialFundamentals.as_of_date.desc())).all()
            if fins:
                fin_df = pd.DataFrame([f.model_dump() for f in fins])
                
                # 确保所有标准列都存在
                for col in FINANCIAL_EXPORT_COLUMNS:
                    if col not in fin_df.columns:
                        fin_df[col] = None
                
                # 按照逻辑顺序重排
                fin_df = fin_df[FINANCIAL_EXPORT_COLUMNS]
                
                # 统一数值缩放 (转换为“亿”)
                financial_value_keywords = ['ttm', 'total_', 'net_', 'cash_', 'income_', 'assets', 'liabilities', 'debt', 'amount', 'equity', 'expense', 'profit', 'loans', 'balance', 'capex', 'dividends_paid']
                exclude_keywords = ['ratio', 'yield', 'percent', 'eps', 'payout', 'coverage', 'date', 'type', 'source', 'currency', 'created']
                
                cols_to_scale = []
                for col in fin_df.columns:
                    if any(key in col for key in financial_value_keywords) and not any(ex in col for ex in exclude_keywords):
                        cols_to_scale.append(col)
                
                for c in cols_to_scale:
                    fin_df[c] = fin_df[c].apply(lambda x: round(x / 100_000_000, 4) if pd.notnull(x) and isinstance(x, (int, float)) else x)
                
                # --- 新增: 优化时间类列显示 (Excel 适配) ---
                if 'created_at' in fin_df.columns:
                    # 移除毫秒，格式化为 YYYY-MM-DD HH:MM:SS
                    fin_df['created_at'] = pd.to_datetime(fin_df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # 确保日期列是干净的字符串 YYYY-MM-DD
                for date_col in ['as_of_date', 'filing_date']:
                    if date_col in fin_df.columns:
                        # 尝试转换，并处理空值
                        fin_df[date_col] = pd.to_datetime(fin_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')

                # 重命名表头，加上单位提示
                rename_map = {c: f"{c} (亿)" for c in cols_to_scale}
                fin_df.rename(columns=rename_map, inplace=True)
                
                output_file = f"{output_dir}/financial_history.csv"
                fin_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"✅ 财报历史导出成功: {len(fin_df)} 条记录, 列数: {len(fin_df.columns)}")
            else:
                print("⚠️ 无财报数据可导出")
            
            # 2. 导出日线表
            print("正在导出 market_daily.csv ...")
            daily = session.exec(select(MarketDataDaily).order_by(MarketDataDaily.symbol, MarketDataDaily.timestamp.desc())).all()
            if daily:
                daily_df = pd.DataFrame([d.model_dump() for d in daily])
                # 排除 id
                if 'id' in daily_df.columns: daily_df = daily_df.drop(columns=['id'])
                daily_df.to_csv(f"{output_dir}/market_daily.csv", index=False, encoding='utf-8-sig')
                print(f"✅ 行情历史导出成功: {len(daily_df)} 条记录")
            else:
                print("⚠️ 无行情数据可导出")
                
            print(f"\n🏁 导出完成! 文件位于 {os.path.abspath(output_dir)}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ 导出失败: {e}")

if __name__ == "__main__":
    main()
