"""
外汇汇率历史数据获取脚本 (fetch_forex_rates.py)
==============================================================================

功能说明:
本脚本通过 Yahoo Finance (`yfinance`) 下载 USD/CNY 和 USD/HKD 的历史汇率数据，
并写入数据库 `ForexRate` 表，为系统内多市场估值计算提供汇率支撑。

背景 (为何需要汇率数据):
VERA 系统同时持有 HK / CN / US 三地资产，财报货币可能与市价货币不一致，典型场景：
- 港股 H 股: 股价为 HKD，但财报可能以 CNY 计（如 601919 中远海控 H 股）。
- 美股 ADR: 股价为 USD，但基础财报可能是 CNY（如 BABA / PDD 等）。
汇率数据使系统能在计算 PE / PB 时进行精确的跨币种调整。

存储数据对 (Canonical Pairs):
- USD → CNY: Yahoo 符号 `CNY=X`（返回值为每 1 USD 兑换多少 CNY）
- USD → HKD: Yahoo 符号 `HKD=X`（返回值为每 1 USD 兑换多少 HKD）

Upsert 逻辑:
- 对每个 (date, from_currency, to_currency) 三元组执行 UPSERT。
- 若已存在则更新 rate 和 updated_at；若不存在则插入新记录。

默认历史深度: 5 年 (1826 天)

依赖:
- `backend.models.ForexRate`: 汇率存储模型
- `backend.database.engine`: 数据库连接

使用方法:
    python3 fetch_forex_rates.py

作者: Antigravity
日期: 2026-01-23
"""


import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from sqlmodel import Session, select
from backend.models import ForexRate
from backend.database import engine

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_forex_history(pair_symbol: str, from_curr: str, to_curr: str, days: int = 365*5):
    """
    Fetch historical forex rates from Yahoo Finance.
    pair_symbol: e.g., 'CNY=X' for USD/CNY (rate 1 USD = x CNY)
    """
    logger.info(f"Fetching history for {pair_symbol} ({from_curr}->{to_curr})...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        df = yf.download(pair_symbol, start=start_date, end=end_date, progress=False)
        if df.empty:
            logger.warning(f"No data found for {pair_symbol}")
            return

        # Handle yfinance multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            # If 'Close' is at top level
            if 'Close' in df.columns.get_level_values(0):
               df = df.xs('Close', axis=1, level=0, drop_level=True)
        
        # If we still have multi-level columns (e.g. from single ticker download structure change), flatten it or take first col
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)

        # Ensure we have a straightforward DF with just rate or just one column
        if len(df.columns) > 1 and 'Close' in df.columns:
            df = df[['Close']]
        
        records_to_add = []
        with Session(engine) as session:
            for date_idx, row in df.iterrows():
                # date_idx should be Timestamp
                date_str = date_idx.strftime('%Y-%m-%d')
                
                # row might be a Series (if multiple cols) or scalar (if one col? No, iterrows always yields Series)
                # If df has 1 column, row is a Series with name=index, value=column value
                if len(row) >= 1:
                    rate_val = float(row.iloc[0])
                else:
                    continue
                
                # Check existence
                existing = session.exec(
                    select(ForexRate).where(
                        ForexRate.date == date_str,
                        ForexRate.from_currency == from_curr,
                        ForexRate.to_currency == to_curr
                    )
                ).first()
                
                if existing:
                    existing.rate = rate_val
                    existing.updated_at = datetime.utcnow()
                    session.add(existing)
                else:
                    new_rate = ForexRate(
                        date=date_str,
                        from_currency=from_curr,
                        to_currency=to_curr,
                        rate=rate_val
                    )
                    session.add(new_rate)
            
            session.commit()
            logger.info(f"Updated {len(records_to_add) if records_to_add else 'rows'} for {pair_symbol}")

    except Exception as e:
        logger.error(f"Error fetching {pair_symbol}: {e}")

def main():
    # Define pairs to fetch
    # Yahoo Tickers:
    # CNY=X -> USD to CNY rate (1 USD = ~7.2 CNY)
    # HKD=X -> USD to HKD rate (1 USD = ~7.8 HKD)
    
    # We primarily need:
    # USD -> CNY (for visualizing US assets in CNY? Or normalizing?)
    # Usually we need to convert everything to a base currency if we were aggregating,
    # but for PE calculation, we need to convert Market Cap currency to Financial Reporting currency if they differ.
    # Case 1: Stock Price in HKD, Financials in CNY (common for H-shares). Need CNY -> HKD or HKD -> CNY.
    # Case 2: Stock Price in USD, Financials in CNY (US listed Chinese ADs). Need CNY -> USD.
    
    # Let's verify what 'CNY=X' gives. It gives CNY per USD.
    # So Rate(USD->CNY) = 'CNY=X'.
    # Rate(CNY->USD) = 1 / 'CNY=X'.
    
    # Strategy: Store canonical pairs.
    # USD/CNY (from='USD', to='CNY')
    # USD/HKD (from='USD', to='HKD')
    
    pairs = [
        ('CNY=X', 'USD', 'CNY'),
        ('HKD=X', 'USD', 'HKD'),
        # Add others if needed, e.g. CNH=X for offshore, but CNY is standard.
    ]
    
    for ticker, from_c, to_c in pairs:
        fetch_forex_history(ticker, from_c, to_c)

if __name__ == "__main__":
    main()
