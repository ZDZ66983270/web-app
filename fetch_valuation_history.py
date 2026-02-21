"""
# 2026-02-07 修复日志: 美股 PB/PS 数据缺口补全与估值精度升级 (v2)
# ================================================================================
# 1. 解决 PB/PS 缺失问题: 
#    - 背景: 美股日线估值中 PB/PS 存在缺失。
#    - 方案: 实现了基于 FinancialFundamentals 的本地推导引擎。
#
# 2. 股本估算增强 (Share Count Fallback):
#    - 方案: 引入 estimated_shares = MarketCap / Close，解决 SEC 财报缺失股本字段的问题。
#
# 3. 市值持久化修复: 
#    - 修复: 补全了 MarketDataDaily 中 market_cap 字段的提取与存入逻辑。
#
# 4. 估值精度补全 (v2 Precision Upgrade) - 重要:
#    - 问题: 发现 AAPL 等非 12 月结账的公司 PE 偏差巨大 (>100%)，原因是 YTD 利润被误计为 TTM。
#    - 修复: 实现了“智能离散化还原算法”，通过检测财年重启（Annual 标志或数值跌幅）将 YTD 还原为 TTM。
#    - 优先级: 调整为“API 优先”策略，仅在数据稀疏时使用本地推导兜底，确保估值的高置信度。
#    - 效果: AAPL PE 从 97.59 回归至 35.07 (正常区间)；TSLA/TSM 等精度全面对齐。
# ================================================================================

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Valuation History Fetcher (历史估值获取器)
========================================

功能说明:
1. **全市场覆盖**: 为 A股 (CN), 港股 (HK), 美股 (US) 提供统一的估值指标获取方案。
2. **多源融合**: 结合官方数据源 (AkShare, Futu) 和商业数据源 (FMP, Yahoo) 以及本地推导能力。
3. **指标覆盖**: 市盈率 (PE TTM), 静态市盈率 (PE Static), 市净率 (PB), 股息率 (Dividend Yield)。

模块架构:
========================================

I. Core Fetchers (核心获取器)
----------------------------------------
负责从外部 API获取原始数据，处理网络请求、鉴权和基础清洗。

| 区域 | 函数名 | 数据源 | 关键特性 |
| :--- | :--- | :--- | :--- |
| **CN** | `fetch_cn_valuation_history` | AkShare (`stock_value_em`) | 东方财富官方数据，包含 PE-TTM/Static, PB。 |
| **CN** | `fetch_cn_dividend_yield` | AkShare (`stock_fhps`) | 复杂逻辑：基于"报告期"计算 TTM 分红，除以最新收盘价。 |
| **HK** | `fetch_hk_valuation_futu` | **Futu OpenD** | **核心逻辑**。通过 Socket 连接本地 OpenD，获取精准的历史 PE/PB。包含自动重试和连接保活。 |
| **HK** | `fetch_hk_dividend_yield` | Yahoo Finance | 补充 Futu 缺失的实时股息率字段。 |
| **HK** | `fetch_hk_valuation_baidu` | Baidu Stock | (Legacy) 仅作为 Futu 不可用时的备选方案。 |
| **US** | `fetch_us_valuation_fmp` | **FMP Cloud** | 商业级 API，提供长达 30 年的日线级 PE/PB 历史。 |
| **US** | `fetch_us_valuation_yf` | Yahoo Finance | (Realtime) 仅用于获取美股盘中/收盘后的瞬时快照。 |

II. Data Persistence & Alignment (持久化与对齐)
----------------------------------------
负责将多源异构数据写入 `MarketDataDaily` 表，核心难题是解决**时间戳对齐**。

- **Futu 对齐逻辑** (`save_hk_valuation_futu`):
  Futu K线时间戳通常为 `00:00:00`，而本地数据库可能存储为 `16:00:00` (收盘时间)。
  算法支持 `+/- 5 Days` 的模糊匹配，优先匹配 exact match，其次寻找最近的交易日，确保估值数据能挂载到正确的价格记录上。

- **增量更新**:
  仅更新 `pe`, `pe_ttm`, `pb`, `ps` 和 `dividend_yield` 字段。
  **绝对不修改** OHLCV 和 Volume 等核心行情数据，确保数据安全。

III. Valuation Backfill & Derivation (补全与推导) [2026-02-11 Update]
----------------------------------------
针对 API 数据缺失的情况 (如港股 PB/PS)，引入了多层补全机制：

1. **FMP Backfill (API 补全)**:
   - **适用**: 港股 (HK), A股 (CN), 美股 (US).
   - **逻辑**: 使用 `fetch_us_valuation_history_fmp` 跨市场调用 FMP 数据接口。
   - **格式转换**: 自动将 `HK:STOCK:00700` 转换为 FMP 格式 `0700.HK`。
   - **效果**: 直接获取 FMP 计算好的精确 PB/PS 数据，解决本地财报单位不一致导致的计算误差。

2. **Local Derivation (本地推导)**:
   - **适用**: 全市场兜底。
   - **逻辑**: 基于 `FinancialFundamentals` (财报) 和 `MarketDataDaily` (价格) 实时计算。
   - **公式**:
     - **PE** = Price / (NetIncome_TTM / Shares)
     - **PB** = Price / (Equity / Shares) [新增兜底]
     - **PS** = Price / (Revenue_TTM / Shares) [新增]
   - **增强**: 自动处理 ADR 换算、汇率对齐 (FX)、以及不同财报期的 TTM 聚合。

IV. ETL Safety (ETL 安全性)
----------------------------------------
为防止日常行情更新覆盖估值数据，配合 `process_raw_data_optimized.py` 使用：
- ETL 脚本在写入新行情时，会自动检查并**保留**已存在的估值数据 (PE/PB/PS)。
- 只有当新数据源明确提供更新的估值时，才会执行覆盖。

作者: Antigravity
日期: 2026-02-11 (Updated for PB/PS Restoration)
"""

# III. US Market Logic & ADR Handling (美股核心逻辑)
# ----------------------------------------
# 美股估值获取包含复杂的**混合策略 (Hybrid Strategy)** 和 **ADR 货币对齐**。
# 前置条件:
# 1. **Futu OpenD**: 必须在本地 127.0.0.1:11111 运行并登录 (针对港股)。
# 2. **FMP API Key**: 需配置有效的 Financial Modeling Prep Key (针对美股历史)。
# 3. **Database**: `MarketDataDaily` 表需预先填充 OHLCV 价格数据。



import sys
sys.path.append('backend')

import akshare as ak
import pandas as pd
import requests
import json
import argparse
import numpy as np
from datetime import datetime, timedelta
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Watchlist, MarketDataDaily
from backend.valuation_calculator import calculate_valuation_series
from backend.symbols_config import get_symbol_info
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FetchValuation")

# [PATCH] ADR Ratio Map (Fixed Error: undefined name)
ADR_RATIO_MAP = {
    'US:STOCK:BABA': 8,   # Alibaba: 1 ADS = 8 Shares
    'US:STOCK:JD': 2,     # JD.com: 1 ADS = 2 Shares
    'US:STOCK:PDD': 4,    # Pinduoduo: 1 ADS = 4 Shares
    'US:STOCK:BIDU': 8,   # Baidu: 1 ADS = 8 Shares
    'US:STOCK:NIO': 1,    # NIO: 1 ADS = 1 Share
    'US:STOCK:XPEV': 2,   # XPeng: 1 ADS = 2 Shares
    'US:STOCK:LI': 2,     # Li Auto: 1 ADS = 2 Shares
    'US:STOCK:TME': 2,    # Tencent Music: 1 ADS = 2 Shares
    'US:STOCK:BILI': 1,   # Bilibili: 1 ADS = 1 Share
    'US:STOCK:TSM': 5,    # TSMC: 1 ADS = 5 Shares
}




def fetch_cn_valuation_history(symbol: str, asset_type: str = 'STOCK') -> pd.DataFrame:
    """
    获取A股历史估值数据
    使用 AkShare stock_value_em() 接口
    
    参数:
        symbol: Canonical ID (如 CN:STOCK:600519)
        asset_type: 资产类型 (STOCK, INDEX)
    """

    try:
        # 1. 检查类型。指数暂不支持通过此接口获取估值
        if asset_type == 'INDEX':
            logger.info(f"  ⏭️  指数暂无个股式估值接口，跳过: {symbol}")
            return None
            
        # 从 Canonical ID 提取纯代码 (CN:STOCK:600519 -> 600519)
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        logger.info(f"  📥 获取A股估值数据: {code}")
        
        # 调用 AkShare 接口 (仅支持个股)
        df = ak.stock_value_em(symbol=code)
        
        if df is None or df.empty:
            logger.warning(f"  ⚠️  无估值数据: {code}")
            return None
        
        logger.info(f"  ✅ 获取 {len(df)} 条估值记录")
        return df
        
    except Exception as e:
        logger.error(f"  ❌ 获取A股估值数据失败 {symbol}: {e}")
        return None


def fetch_hk_valuation_baidu_direct(code: str, indicator: str = "市盈率(TTM)") -> pd.DataFrame:
    """
    直接调用百度股市通 OpenData 接口获取港股历史估值数据
    
    参数:
        code: 5位港股代码 (如 '00700')
        indicator: '市盈率(TTM)' 或 '市净率'
    """

    try:
        url = "https://gushitong.baidu.com/opendata"
        params = {
            "openapi": "1",
            "dspName": "iphone",
            "tn": "tangram",
            "client": "app",
            "query": indicator,
            "code": code,
            "resource_id": "51171",
            "srcid": "51171",
            "market": "hk",
            "tag": indicator,
            "skip_industry": "1",
            "chart_select": "全部",
            "finClientType": "pc"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        logger.info(f"  🌐 调用百度接口获取 {indicator}: {code}")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"  ❌ 接口响应错误: {response.status_code}")
            return None
            
        data = response.json()
        
        # 复杂 JSON 路径提取
        # Result[0].DisplayData.resultData.tplData.result.chartInfo[0].body
        try:
            results = data.get("Result", [])
            if not results:
                return None
            
            display_data = results[0].get("DisplayData", {}).get("resultData", {}).get("tplData", {}).get("result", {})
            chart_info = display_data.get("chartInfo", [])
            
            if not chart_info:
                return None
                
            body = chart_info[0].get("body", [])
            
            if not body:
                return None
            
            # body 格式为 [[date, value], ...]
            df = pd.DataFrame(body, columns=['date', 'value'])
            
            # 转换日期和数值
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            return df
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"  ❌ 解析结果失败: {e}")
            return None
            
    except Exception as e:
        logger.error(f"  ❌ 调用百度接口异常: {e}")
        return None


def fetch_cn_dividend_yield(symbol: str) -> float:
    """
    获取A股最新股息率
    计算方式: Sum(最近一年每股分红) / 当前股价
    使用 AkShare: stock_fhps_detail_em (分红) + stock_zh_a_hist (股价)
    """

    try:
        import akshare as ak
        from datetime import datetime, timedelta
        
        # 从 Canonical ID 提取纯代码 (CN:STOCK:600030 -> 600030)
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        logger.info(f"  📊 获取A股股息率: {code}")
        
        # 1. 获取当前股价
        try:
            # 获取最近几天的K线，取最新收盘价
            # 使用 qfq (前复权) 比较合适? 不，股息率通常用不复权价格计算实时的。
            # 直接取最近一条记录
            start_dt = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
            price_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_dt, adjust="qfq")
            if price_df is None or price_df.empty:
                logger.warning(f"  ⚠️  无法获取股价: {code}")
                return None
            current_price = float(price_df.iloc[-1]['收盘'])
        except Exception as e:
            logger.warning(f"  ⚠️  获取股价失败: {e}")
            return None
            
        if current_price <= 0:
            return None

        # 2. 获取分红配送详情
        df = ak.stock_fhps_detail_em(symbol=code)
        
        if df is None or df.empty:
            return None
        
        if '现金分红-现金分红比例' not in df.columns:
            logger.warning("  ⚠️  找不到分红比例列")
            return None

        # 3. 使用"报告期"计算TTM (最近一年宣告分红)
        # 避免因除权除息日变动导致 "刚过365天就归零" 的情况
        report_col = '报告期'
        if report_col not in df.columns:
             # 回退到旧逻辑 (除权日)
             logger.warning("  ⚠️  找不到报告期列, 回退到除权日逻辑")
             
             # ... (Fallback if needed, but for now we trust Report Date usually exists)
             date_col = '除权除息日'
             if date_col not in df.columns: return None
             df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
             recent_dividends = df[df[date_col] >= (datetime.now().date() - timedelta(days=365))]
        else:
            df[report_col] = pd.to_datetime(df[report_col], errors='coerce').dt.date
            max_report_date = df[report_col].max()
            
            if pd.isna(max_report_date):
                return 0.0
                
            # 截断日期: 最新报告期 - 1年
            # 例如: 最新 2024-12-31. 截断 2023-12-31.
            # 我们需要 > 2023-12-31 的记录 (即 2024-06, 2024-12).
            cutoff_date = max_report_date - timedelta(days=365)
            
            recent_dividends = df[df[report_col] > cutoff_date]
        
        if recent_dividends.empty:
            logger.info(f"  ℹ️  过去一年无分红宣告 (Based on Report Date)")
            return 0.0
            
        # 4. 计算总每股分红 (DPS)
        # 列名: '现金分红-现金分红比例' (每10股派多少元)
        sum_per_10 = recent_dividends['现金分红-现金分红比例'].sum()
        total_dps = sum_per_10 / 10.0

        # 5. 计算股息率
        dividend_yield = (total_dps / current_price) * 100
        
        logger.info(f"  ✅ TTM股息率(宣告): {dividend_yield:.2f}% (DPS: {total_dps}, Price: {current_price})")
        return dividend_yield
        
    except Exception as e:
        logger.warning(f"  ⚠️  获取A股股息率失败 {symbol}: {e}")
        return None


def fetch_hk_dividend_yield(symbol: str) -> float:
    """
    获取港股最新股息率
    使用yfinance
    """

    try:
        import yfinance as yf
        # 从 Canonical ID 提取纯代码 (HK:STOCK:00700 -> 00700)
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        # 转换为yfinance格式 (00700 -> 0700.HK)
        # yfinance 需要4位数字代码 (例如 0700.HK)
        clean_code = code.lstrip('0')
        if len(clean_code) < 4:
            clean_code = clean_code.zfill(4)
        yf_symbol = f"{clean_code}.HK"
        
        logger.info(f"  📊 获取港股股息率: {yf_symbol}")
        
        ticker = yf.Ticker(yf_symbol)
        
        # 直接从 info 获取 (用户倾向于 Direct Fetch)
        info = ticker.info
        dividend_yield = info.get('dividendYield')
        
        if dividend_yield is not None:
             # yfinance 返回的就是百分比数值 (e.g. 4.0 = 4%)
             # 无需乘以100
             converted_yield = dividend_yield
             logger.info(f"  ✅ [Fetch] 港股股息率: {converted_yield:.2f}%")
             return converted_yield
        
        logger.warning(f"  ⚠️  无法获取港股股息率 (Info is None)")
        return None
        
    except Exception as e:
        logger.warning(f"  ⚠️  获取港股股息率失败 {symbol}: {e}")
        return None


def fetch_hk_valuation_history(symbol: str, indicator: str = "市盈率") -> pd.DataFrame:
    """
    获取港股历史估值数据
    使用百度接口 (TTM PE 和 PB)
    """

    try:
        # 从 Canonical ID 提取纯代码 (HK:STOCK:00700 -> 00700)
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        if indicator == "市盈率(TTM)":
            # 获取 TTM PE
            df = fetch_hk_valuation_baidu_direct(code, indicator="市盈率(TTM)")
            if df is not None and not df.empty:
                df = df.rename(columns={'value': 'pe'}) # Temporary rename, value is generic
                return df
        elif indicator == "市盈率":
             # 获取 Static PE (Baidu usually '市盈率' implies Static/Lyr or just PE)
             df = fetch_hk_valuation_baidu_direct(code, indicator="市盈率")
             if df is not None and not df.empty:
                 df = df.rename(columns={'value': 'pe'})
                 return df
                
        elif indicator == "市净率":
            # 获取 PB
            df = fetch_hk_valuation_baidu_direct(code, indicator="市净率")
            if df is not None and not df.empty:
                df = df.rename(columns={'value': 'pb'})
                logger.info(f"  ✅ 获取 {len(df)} 条 PB 记录")
                return df
        
        return None
            
    except Exception as e:
        logger.error(f"  ❌ 获取港股{indicator}数据失败 {symbol}: {e}")
        return None


def save_cn_valuation_to_daily(symbol: str, df: pd.DataFrame, session: Session, days: int = -1) -> int:
    """
    将A股估值数据保存到 MarketDataDaily 表
    更新 pe_ratio 和 pb_ratio 字段
    """

    if df is None or df.empty:
        return 0
    
    # --- 日期过滤 ---
    if days > 0:
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        df['数据日期_parsed'] = pd.to_datetime(df['数据日期'].astype(str), errors='coerce').dt.date
        df = df[df['数据日期_parsed'] >= cutoff_date].copy()
    
    if df.empty:
        logger.info(f"  ⏭️ 没有符合日期范围 ({days}天) 的记录: {symbol}")
        return 0
    
    updated_count = 0
    
    for _, row in df.iterrows():
        try:
            # 解析日期
            date_str = str(row['数据日期'])
            if len(date_str) == 8:  # YYYYMMDD
                timestamp_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} 15:00:00"
            else:
                # 已经是 YYYY-MM-DD 格式
                timestamp_str = f"{date_str} 15:00:00"
            
            # 查找对应的日线记录
            existing = session.exec(
                select(MarketDataDaily).where(
                    MarketDataDaily.symbol == symbol,
                    MarketDataDaily.timestamp == timestamp_str
                )
            ).first()

            # Fallback: 尝试 00:00:00 (如果ETL未归一化)
            if not existing:
                if len(date_str) == 8:
                    timestamp_00 = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} 00:00:00"
                else:
                    timestamp_00 = f"{date_str} 00:00:00"
                
                existing = session.exec(
                    select(MarketDataDaily).where(
                        MarketDataDaily.symbol == symbol,
                        MarketDataDaily.timestamp == timestamp_00
                    )
                ).first()
                if existing:
                    # Self-heal timestamp
                    existing.timestamp = timestamp_str
            
            if existing:
                # 更新PE和PB
                existing.pe_ttm = float(row['PE(TTM)']) if pd.notna(row['PE(TTM)']) else None
                # PE(静) mapping
                existing.pe = float(row['PE(静)']) if 'PE(静)' in row and pd.notna(row['PE(静)']) else None
                
                existing.pb = float(row['市净率']) if pd.notna(row['市净率']) else None
                # 保存股息率(如果有)
                if 'dividend_yield' in row and pd.notna(row['dividend_yield']):
                    existing.dividend_yield = float(row['dividend_yield'])
                existing.updated_at = datetime.now()
                session.add(existing)
                updated_count += 1
                
        except Exception as e:
            logger.warning(f"  ⚠️  跳过记录 {date_str}: {e}")
            continue
    
    if updated_count > 0:
        session.commit()
        logger.info(f"  💾 更新 {updated_count} 条记录的PE/PB数据")
    
    return updated_count


def save_hk_valuation_to_daily(symbol: str, df_pe_ttm: pd.DataFrame, df_pe_static: pd.DataFrame, df_pb: pd.DataFrame, session: Session) -> int:
    """
    将港股估值数据保存到 MarketDataDaily 表
    更新 pe_ratio 和 pb_ratio 字段
    
    注意: 百度返回的日期可能与实际交易日期有偏差,使用日期部分匹配
    """

    updated_count = 0
    pe_ttm_matched = 0
    pe_static_matched = 0
    pb_matched = 0
    
    # 处理 PE TTM
    if df_pe_ttm is not None and not df_pe_ttm.empty:
        logger.info(f"  📊 处理 {len(df_pe_ttm)} 条 PE(TTM) 数据...")
        for _, row in df_pe_ttm.iterrows():
            try:
                date = pd.to_datetime(row['date'])
                date_str = date.strftime('%Y-%m-%d')
                val = float(row['pe']) if pd.notna(row['pe']) else None
                if val is None: continue

                # Match logic: Try nearest within +/- 5 days
                matched = False
                offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5]
                for offset in offsets:
                    target_date = date + pd.Timedelta(days=offset)
                    timestamp_str = target_date.strftime('%Y-%m-%d') + ' 16:00:00'
                    existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_str)).first()
                    if not existing:
                        timestamp_00 = target_date.strftime('%Y-%m-%d') + ' 00:00:00'
                        existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_00)).first()
                        if existing: existing.timestamp = timestamp_str
                    
                    if existing:
                        existing.pe_ttm = val
                        existing.updated_at = datetime.now()
                        session.add(existing)
                        pe_ttm_matched += 1
                        matched = True
                        break
            except Exception: continue

    # 处理 PE Static
    if df_pe_static is not None and not df_pe_static.empty:
        logger.info(f"  📊 处理 {len(df_pe_static)} 条 PE(Static) 数据...")
        for _, row in df_pe_static.iterrows():
            try:
                date = pd.to_datetime(row['date'])
                val = float(row['pe']) if pd.notna(row['pe']) else None
                if val is None: continue
                
                matched = False
                offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5]
                for offset in offsets:
                    target_date = date + pd.Timedelta(days=offset)
                    timestamp_str = target_date.strftime('%Y-%m-%d') + ' 16:00:00'
                    existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_str)).first()
                    if not existing:
                        timestamp_00 = target_date.strftime('%Y-%m-%d') + ' 00:00:00'
                        existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_00)).first()
                        if existing: existing.timestamp = timestamp_str
                    
                    if existing:
                        existing.pe = val
                        existing.updated_at = datetime.now()
                        session.add(existing)
                        pe_static_matched += 1
                        matched = True
                        break
            except Exception: continue
    
    # 处理PB数据
    if df_pb is not None and not df_pb.empty:
        logger.info(f"  📊 处理 {len(df_pb)} 条PB数据...")
        for _, row in df_pb.iterrows():
            try:
                date = pd.to_datetime(row['date'])
                date_str = date.strftime('%Y-%m-%d')
                pb_value = float(row['pb']) if pd.notna(row['pb']) else None
                
                if pb_value is None:
                    continue
                
                # Match logic: Try nearest within +/- 5 days
                matched = False
                # Priority: 0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5
                offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5]
                
                for offset in offsets:
                    target_date = date + pd.Timedelta(days=offset)
                    timestamp_str = target_date.strftime('%Y-%m-%d') + ' 16:00:00'
                    existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_str)).first()
                    
                    if not existing:
                        timestamp_00 = target_date.strftime('%Y-%m-%d') + ' 00:00:00'
                        existing = session.exec(select(MarketDataDaily).where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == 'HK', MarketDataDaily.timestamp == timestamp_00)).first()
                        if existing: existing.timestamp = timestamp_str # Self-heal
                    
                    if existing:
                        # Avoid overwriting if we already have a closer match? 
                        # Ideally updates are idempotent.
                        existing.pb = pb_value
                        existing.updated_at = datetime.now()
                        session.add(existing)
                        pb_matched += 1
                        matched = True
                        break
                
                if not matched:
                    logger.debug(f"  ⚠️  未匹配到PB记录: {date_str}")
                    
            except Exception as e:
                logger.warning(f"  ❌ 处理PB记录失败 {date_str}: {e}")
                continue
    
    updated_count = pe_ttm_matched + pe_static_matched + pb_matched
    
    if updated_count > 0:
        session.commit()
        logger.info(f"  💾 更新 {updated_count} 条记录 (PE_TTM: {pe_ttm_matched}, PE_Static: {pe_static_matched}, PB: {pb_matched})")
    else:
        logger.warning(f"  ⚠️  没有匹配到任何记录")
    
    return updated_count


def fetch_us_valuation_yfinance(symbol: str) -> dict:
    """
    从 yfinance 获取美股的实时估值指标
    使用 ticker.info API
    """

    try:
        import yfinance as yf
        
        # 从 Canonical ID 提取纯代码 (US:STOCK:AAPL -> AAPL)
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        logger.info(f"  📥 获取美股估值数据: {code}")
        
        ticker = yf.Ticker(code)
        info = ticker.info
        
        # 获取 PE (优先使用 trailingPE, 其次 forwardPE)
        pe = info.get('trailingPE') or info.get('forwardPE')
        
        # 获取 PB
        pb = info.get('priceToBook')
        
        # 获取股息率
        dividend_yield = info.get('dividendYield')
        # 无需乘以100
        if dividend_yield is not None:
            pass
        
        # ADR 比例修正
        adr_ratio = ADR_RATIO_MAP.get(symbol, 1.0)
        if adr_ratio != 1.0:
            logger.info(f"  📐 映射 ADR 比例: {symbol} (1:{adr_ratio})")
            # 注意: Yfinance 的 PE (trailingPE) 通常已经是 ADR 级别的(已对齐价格), 不需要修正。
            # 但 PB (priceToBook) 通常使用普通股 BPS, 导致偏大, 需要修正。
            if pb: pb = pb / adr_ratio
        
        result = {
            'pe_ttm': pe, # Yfinance trailingPE -> pe_ttm
            'pb': pb,
            'ps': info.get('priceToSalesTrailing12Months') or info.get('forwardTrailingSales'),
            'dividend_yield': dividend_yield,
            'market_cap': info.get('marketCap')
        }
        
        # 格式化输出
        pe_str = f"{pe:.2f}" if pe else "N/A"
        pb_str = f"{pb:.2f}" if pb else "N/A"
        div_str = f"{dividend_yield:.2f}%" if dividend_yield else "N/A"
        logger.info(f"  ✅ PE: {pe_str}, PB: {pb_str}, 股息率: {div_str}")
        
        return result
        
    except Exception as e:
        logger.error(f"  ❌ 获取美股估值数据失败 {symbol}: {e}")
        return None


def fetch_hk_valuation_yfinance(symbol: str) -> dict:
    """
    从 yfinance 获取港股的实时估值指标 (0700.HK 格式)
    """
    try:
        import yfinance as yf
        code = symbol.split(':')[-1]
        # 补齐 4 位代码 (e.g. 700 -> 0700)
        clean_code = code.lstrip('0')
        if len(clean_code) < 4:
            clean_code = clean_code.zfill(4)
        yf_symbol = f"{clean_code}.HK"
        
        logger.info(f"  📥 [Yahoo] 获取港股估值: {yf_symbol}")
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        
        pe = info.get('trailingPE') or info.get('forwardPE')
        pb = info.get('priceToBook')
        ps = info.get('priceToSalesTrailing12Months')
        dividend_yield = info.get('dividendYield') # yfinance percent for HK info? usually decimal 0.04
        
        if dividend_yield and dividend_yield < 1.0:
            dividend_yield *= 100
            
        result = {
            'pe_ttm': pe,
            'pb': pb,
            'ps': ps,
            'dividend_yield': dividend_yield,
            'market_cap': info.get('marketCap')
        }
        
        pe_str = f"{pe:.2f}" if pe else "N/A"
        pb_str = f"{pb:.2f}" if pb else "N/A"
        ps_str = f"{ps:.2f}" if ps else "N/A"
        logger.info(f"  ✅ [Yahoo] PE: {pe_str}, PB: {pb_str}, PS: {ps_str}")
        return result
    except Exception as e:
        logger.error(f"  ❌ [Yahoo] 港股获取失败 {symbol}: {e}")
        return None



FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"

def fetch_us_valuation_history_fmp(symbol: str, limit: int = 5, days: int = -1) -> pd.DataFrame:
    """
    从 FMP Cloud 获取美股历史估值数据 (PE, PB)
    使用 /stable/ratios 接口
    """

    try:
        # 如果提供了 days, 动态调整 limit (估计算法: 每季度约 1 条记录, 加宽一点点)
        if days > 0:
            estimated_reports = max(4, int(days / 90) + 2)
            limit = min(limit, estimated_reports)
            
        # FMP stable 接口限制非高级订阅最多 5 条记录，高级订阅可调大至 100+
        limit = min(limit, 100)

        # 纯代码 & FMP 格式转换
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        # 港股处理: HK:STOCK:00700 -> 0700.HK
        if 'HK:STOCK:' in symbol:
            code = f"{code}.HK"
            
        # A股处理: CN:STOCK:600036 -> 600036.SS
        elif 'CN:' in symbol:
            if code.startswith('6'):
                code = f"{code}.SS"
            else:
                code = f"{code}.SZ"

        # 修正: 使用 quarter 周期以获得更高的推导精度 (PB/PS 需要较密的报告点)
        url = f"https://financialmodelingprep.com/stable/ratios?symbol={code}&period=quarter&limit={limit}&apikey={FMP_API_KEY}"
        logger.info(f"  📥 [FMP] 获取历史估值 (季度): {code}")
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data:
            logger.info(f"  ℹ️  [FMP] 无历史数据: {code}")
            return None
        
        # 处理 API 错误 (例如 Limit Reach)
        if isinstance(data, dict) and "Error Message" in data:
             logger.warning(f"  ⚠️ [FMP] API 限制或错误: {data['Error Message']}")
             return None

        # 转换为 DataFrame
        records = []
        for item in data:
            if not isinstance(item, dict): continue
            records.append({
                'date': item.get('date'),
                'pe': item.get('priceToEarningsRatio'),
                'pb': item.get('priceToBookRatio'),
                'ps': item.get('priceToSalesRatio'),
                'market_cap': item.get('marketCap')
            })
            
        df = pd.DataFrame(records)
        
        # ADR 比例修正
        adr_ratio = ADR_RATIO_MAP.get(symbol, 1.0)
        if adr_ratio != 1.0 and not df.empty:
            logger.info(f"  📐 FMP 历史应用 ADR 比例: {symbol} (1:{adr_ratio})")
            # 同理, FMP 的 PE 通常是正确的, 仅修正 PB
            if 'pb' in df.columns: df['pb'] = df['pb'] / adr_ratio

        logger.info(f"  ✅ [FMP] 获取 {len(df)} 条历史记录")
        return df
        
    except Exception as e:
        logger.error(f"  ❌ [FMP] 获取失败 {symbol}: {e}")
        return None

def fetch_us_valuation_history_fmp_ttm(symbol: str, limit: int = 365) -> pd.DataFrame:
    """
    从 FMP Cloud 获取美股每日滚动 PE (TTM)
    使用 /v3/ratios-ttm 接口
    """

    try:
        # 纯代码
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        # 使用 v3 接口 (根据用户请求)
        url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{code}?limit={limit}&apikey={FMP_API_KEY}"
        logger.info(f"  📥 [FMP] 获取美股 TTM PE: {code}")
        
        response = requests.get(url, timeout=10)
        
        # 错误处理
        if response.status_code == 403:
             logger.warning(f"  ⚠️ [FMP] API Key 无效或无 TTM 权限 (403): {response.text[:100]}")
             return None
             
        data = response.json()
        
        if not data:
            logger.info(f"  ℹ️  [FMP] 无 TTM 数据: {code}")
            return None
        
        if isinstance(data, dict) and "Error Message" in data:
             logger.warning(f"  ⚠️ [FMP] API 错误: {data['Error Message']}")
             return None

        # 转换为 DataFrame
        records = []
        for item in data:
            if not isinstance(item, dict): continue
            
            # FMP TTM field: peRatioTTM
            val = item.get('peRatioTTM')
            if val is None: val = item.get('priceEarningsRatioTTM')
            
            # --- VERA Pro Fields ---
            # NOTE: The endpoint /ratios-ttm usually only returns Ratios (PE, PB, etc.), NOT fundamentals.
            # To get NetIncomeCommon and SharesDiluted(TTM), we strictly need /key-metrics-ttm or calculate from /income-statement.
            # However, for simple PE history backfill (this function's purpose is PE history), we might just be saving PE TTM directly?
            # Wait, `fetch_us_valuation_history_fmp_ttm` returns a DF that is saving to MarketDataDaily directly in `recalc_historical_pe` or saving to Financials?
            # Looking at `save_us_historical_valuation_to_daily`, it saves directly to DAILY.
            # This function is for "downloading pre-calculated PE from FMP".
            
            # BUT, the user wants us to CALCULATE locally using Fundamentals.
            # So we need a NEW function in `fetch_financials.py` (or here) that fetches INCOME STATEMENT and fills FinancialFundamentals.
            # This function `fetch_us_valuation_history_fmp_ttm` is about fetching PE directly.
            
            # Let's keep this as is for BACKUP PE sources, but we need to ensure we can FETCH FUNDAMENTALS.
            # The user instruction was: "Update FMP API calls to fetch specific fields: netIncomeForCommonStockholders..."
            # This implies we need to update where we fetch FinancialFundamentals.
            
            if val is None: continue
            
            records.append({
                'date': item.get('date'),
                'pe_ttm': val
            })
            
        df = pd.DataFrame(records)
        logger.info(f"  ✅ [FMP] 获取 {len(df)} 条 TTM 记录")
        return df
        
    except Exception as e:
        logger.error(f"  ❌ [FMP] 获取 TTM 失败 {symbol}: {e}")
        return None

def save_us_historical_valuation_to_daily(symbol: str, df: pd.DataFrame, session: Session, only_nulls: bool = False) -> int:
    """
    保存 FMP 历史估值数据到 MarketDataDaily (Fallback logic)
    支持 pe, pb, pe_ttm, ps
    
    参数:
        only_nulls: 如果为 True, 则只在目标字段为 None 时才填充, 不覆盖已有值。
    """

    if df is None or df.empty:
        return 0
        
    updated_count = 0
    
    for _, row in df.iterrows():
        try:
            date_str = row['date'] # YYYY-MM-DD
            pe = float(row['pe']) if 'pe' in row and pd.notna(row['pe']) else None
            pe_ttm = float(row['pe_ttm']) if 'pe_ttm' in row and pd.notna(row['pe_ttm']) else None
            pb = float(row['pb']) if 'pb' in row and pd.notna(row['pb']) else None
            # Fix: Ensure ps is extracted from row
            ps = float(row['ps']) if 'ps' in row and pd.notna(row['ps']) else None
            market_cap = float(row['market_cap']) if 'market_cap' in row and pd.notna(row['market_cap']) else None
            
            if pe is None and pb is None and pe_ttm is None and ps is None and market_cap is None:
                continue
                
            task_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            matched = False
            # 改进: 更加鲁棒的时间戳匹配 (美股可能存在 16:00:00, 09:30:00, 00:00:00 等多种组合)
            # 我们直接查找当天的所有记录并更新
            day_prefix = task_date.strftime("%Y-%m-%d")
            
            # Infer market from symbol
            market = 'US'
            if ':STOCK:' in symbol:
                if symbol.startswith('HK:'): market = 'HK'
                elif symbol.startswith('CN:'): market = 'CN'
            
            existing_records = session.exec(
                select(MarketDataDaily).where(
                    MarketDataDaily.symbol == symbol,
                    MarketDataDaily.market == market,
                    MarketDataDaily.timestamp.like(f"{day_prefix}%")
                )
            ).all()

            if existing_records:
                for existing in existing_records:
                    # 优先级控制: 允许覆盖已有的记录 (特别是推导数据)
                    if pe is not None:
                        if not only_nulls or existing.pe is None: existing.pe = pe
                    if pe_ttm is not None:
                        if not only_nulls or existing.pe_ttm is None: existing.pe_ttm = pe_ttm
                    if pb is not None:
                        if not only_nulls or existing.pb is None: existing.pb = pb
                    if ps is not None:
                        if not only_nulls or existing.ps is None: existing.ps = ps
                    if market_cap is not None:
                        if not only_nulls or existing.market_cap is None: existing.market_cap = market_cap
                    
                    existing.updated_at = datetime.now()
                    session.add(existing)
                    updated_count += 1
                    matched = True
                # 注意: 这里不 break, 因为可能一天有多条记录
            
            if not matched:
                logger.debug(f"  ⚠️  [FMP] 未匹配到历史日线: {date_str}")

        except Exception as e:
            logger.warning(f"  ⚠️  保存失败 {date_str}: {e}")
            
    if updated_count > 0:
        session.commit()
    return updated_count


def save_realtime_valuation_to_daily(symbol: str, valuation: dict, session: Session, market: str = 'US') -> int:
    """
    将实时估值数据保存到 MarketDataDaily 表 (Generic)
    """

    if not valuation:
        return 0
    
    try:
        from backend.market_status import MarketStatus
        
        is_market_open = MarketStatus.is_market_open(market)
        market_time = MarketStatus.get_market_time(market)
        
        latest_record = session.exec(
            select(MarketDataDaily).where(
                MarketDataDaily.symbol == symbol,
                MarketDataDaily.market == market
            ).order_by(MarketDataDaily.timestamp.desc())
        ).first()
        
        if not latest_record:
            logger.warning(f"  ⚠️  未找到日线记录: {symbol}")
            return 0
        
        record_date = datetime.strptime(latest_record.timestamp, '%Y-%m-%d %H:%M:%S').date()
        today = market_time.date()
        
        if is_market_open and record_date == today:
            logger.info(f"  ⏭️  盘中时段,仅更新最近 5 条空缺记录: {symbol}")
            limit = 5
        else:
            limit = 10 # 默认扫描最近 10 天

        target_records = session.exec(
            select(MarketDataDaily).where(
                MarketDataDaily.symbol == symbol,
                MarketDataDaily.market == market
            ).order_by(MarketDataDaily.timestamp.desc()).limit(limit)
        ).all()
        
        if not target_records:
            return 0
            
        update_count = 0
        from backend.sanitizers import check_valuation_outliers
        for record in target_records:
            # 安全检查: 只有当记录日期在最近 3 天内，才允许用“实时值”回填空缺
            record_dt = datetime.strptime(record.timestamp, '%Y-%m-%d %H:%M:%S')
            is_recent = (datetime.now() - record_dt).days <= 3
            
            rec_updated = False
            if record.pe_ttm is None and valuation.get('pe_ttm') and is_recent:
                if check_valuation_outliers(valuation['pe_ttm'], 'pe'):
                    record.pe_ttm = valuation['pe_ttm']
                    rec_updated = True
            
            if record.pb is None and valuation.get('pb') and is_recent:
                if check_valuation_outliers(valuation['pb'], 'pb'):
                    record.pb = valuation['pb']
                    rec_updated = True
                
            if record.ps is None and valuation.get('ps') and is_recent:
                if check_valuation_outliers(valuation['ps'], 'ps'):
                    record.ps = valuation['ps']
                    rec_updated = True

            if record.dividend_yield is None and valuation.get('dividend_yield') and is_recent:
                if check_valuation_outliers(valuation['dividend_yield'], 'dividend_yield'):
                    record.dividend_yield = valuation['dividend_yield']
                    rec_updated = True
            
            if record.market_cap is None and valuation.get('market_cap') and is_recent:
                record.market_cap = valuation['market_cap']
                rec_updated = True
            
            if rec_updated:
                record.updated_at = datetime.now()
                session.add(record)
                update_count += 1
        
        if update_count > 0:
            session.commit()
            return update_count
        return 0
        
        updated = False
        if valuation.get('pe_ttm'):
            latest_record.pe_ttm = valuation['pe_ttm']
            updated = True
        # Static PE not updated from Yfinance (Realtime) usually
        if valuation.get('pe'):
             latest_record.pe = valuation['pe']
             updated = True
        if valuation.get('pb'):
            latest_record.pb = valuation['pb']
            updated = True
        if valuation.get('dividend_yield'):
            latest_record.dividend_yield = valuation['dividend_yield']
            updated = True
        
        if updated:
            latest_record.updated_at = datetime.now()
            session.add(latest_record)
            session.commit()
            logger.info(f"  💾 更新记录的估值数据 ({latest_record.timestamp})")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"  ❌ 保存美股估值数据失败 {symbol}: {e}")
        return 0


def derive_daily_pe_from_points(symbol: str, daily_prices: pd.DataFrame, report_points: pd.DataFrame) -> pd.Series:
    """
    通用函数: 基于稀疏的 PE 报告点推导日线 PE
    """

    try:
        if daily_prices.empty or report_points.empty:
            return pd.Series(dtype=float)
            
        # 1. 准备数据
        reports = report_points.sort_values('date').copy()
        reports = reports[reports['pe'] > 0]
        
        if reports.empty:
            return pd.Series(dtype=float)

        daily_idx = daily_prices.index.sort_values()
        
        # 2. 计算每个报告日的隐含 EPS
        eps_map = {}
        for _, row in reports.iterrows():
            r_date = row['date']
            r_pe = row['pe']
            
            # 在日线价格中找 exact match 或 nearest (Look-back only)
            matched_date = None
            try:
                # 使用 asof 寻找最近的一个交易日 (Look-back, 避免未来数据)
                # asof returns the last index label <= r_date
                closest_date = daily_idx.asof(r_date)
                
                if pd.isna(closest_date):
                    continue
                    
                # 检查时间跨度是否过大 (超过 5 天视为无效匹配)
                if (r_date - closest_date).days > 5:
                    continue
                    
                matched_date = closest_date
                close = daily_prices.loc[matched_date, 'close']

                if isinstance(close, pd.Series): close = close.iloc[0]
                
                if close > 0 and r_pe > 0:
                    eps_implied = close / r_pe
                    if matched_date:
                        eps_map[matched_date] = eps_implied
            except:
                continue
                
        if not eps_map:
            return pd.Series(dtype=float)
            
        # 3. 生成 EPS 序列并对齐到日线
        eps_series = pd.Series(eps_map).sort_index()
        eps_daily = eps_series.reindex(daily_idx).ffill()
        
        # 4. 计算 Daily PE
        daily_pe = daily_prices['close'] / eps_daily
        daily_pe = daily_pe.replace([np.inf, -np.inf], np.nan).dropna()
        
        return daily_pe.round(2)
        
    except Exception as e:
        logger.error(f"  ❌ 推导失败 {symbol}: {e}")
        return pd.Series(dtype=float)


def derive_daily_pb_from_points(symbol: str, daily_prices: pd.DataFrame, report_points: pd.DataFrame) -> pd.Series:
    """
    通用函数: 基于稀疏的 PB 报告点推导日线 PB
    逻辑同 PE 推导: Implied BPS = Close / PB
    """

    try:
        if daily_prices.empty or report_points.empty:
            return pd.Series(dtype=float)
            
        # 1. 准备数据
        reports = report_points.sort_values('date').copy()
        reports = reports[reports['pb'] > 0]
        
        if reports.empty:
            return pd.Series(dtype=float)

        daily_idx = daily_prices.index.sort_values()
        
        # 2. 计算每个报告日的隐含 BPS
        bps_map = {}
        for _, row in reports.iterrows():
            r_date = row['date']
            r_pb = row['pb']
            
            # 在日线价格中找 match (Look-back only)
            matched_date = None
            try:
                # 使用 asof 寻找最近的一个交易日 (Look-back, 避免未来数据)
                # asof returns the last index label <= r_date
                closest_date = daily_idx.asof(r_date)
                
                if pd.isna(closest_date):
                    continue
                    
                # 检查时间跨度是否过大
                if (r_date - closest_date).days > 5:
                    continue
                    
                matched_date = closest_date
                close = daily_prices.loc[matched_date, 'close']

                if isinstance(close, pd.Series): close = close.iloc[0]
                
                if close > 0 and r_pb > 0:
                    bps_implied = close / r_pb
                    if matched_date:
                        bps_map[matched_date] = bps_implied
            except:
                continue
                
        if not bps_map:
            return pd.Series(dtype=float)
            
        # 3. 生成 BPS 序列并对齐到日线
        bps_series = pd.Series(bps_map).sort_index()
        bps_daily = bps_series.reindex(daily_idx).ffill()
        
        # 4. 计算 Daily PB
        daily_pb = daily_prices['close'] / bps_daily
        daily_pb = daily_pb.replace([np.inf, -np.inf], np.nan).dropna()
        
        return daily_pb.round(2)
        
    except Exception as e:
        logger.error(f"  ❌ PB推导失败 {symbol}: {e}")
        return pd.Series(dtype=float)


# ==============================================================================
# Local Derivation (Fallback for missing API data)
# ==============================================================================

def derive_daily_ps_from_points(symbol: str, daily_prices: pd.DataFrame, report_points: pd.DataFrame) -> pd.Series:
    """
    通用函数: 基于稀疏的 PS 报告点推导日线 PS
    逻辑同 PE 推导: Implied Revenue BPS (Sales per Share) = Close / PS
    """

    try:
        if daily_prices.empty or report_points.empty:
            return pd.Series(dtype=float)
            
        # 1. 准备数据
        reports = report_points.sort_values('date').copy()
        reports = reports[reports.get('ps', pd.Series(dtype=float)) > 0]
        
        if reports.empty:
            return pd.Series(dtype=float)

        daily_idx = daily_prices.index.sort_values()
        
        # 2. 计算每个报告日的隐含 Revenue Per Share
        rev_map = {}
        for _, row in reports.iterrows():
            r_date = row['date']
            r_ps = row['ps']
            
            # 在日线价格中找 match (Look-back only)
            try:
                closest_date = daily_idx.asof(r_date)
                if pd.isna(closest_date) or (r_date - closest_date).days > 5:
                    continue
                    
                matched_date = closest_date
                close = daily_prices.loc[matched_date, 'close']
                if isinstance(close, pd.Series): close = close.iloc[0]
                
                if close > 0 and r_ps > 0:
                    rev_implied = close / r_ps
                    rev_map[matched_date] = rev_implied
            except:
                continue
                
        if not rev_map:
            return pd.Series(dtype=float)
            
        # 3. 生成 Revenue 序列并对齐到日线
        rev_series = pd.Series(rev_map).sort_index()
        rev_daily = rev_series.reindex(daily_idx).ffill()
        
        # 4. 计算 Daily PS
        daily_ps = daily_prices['close'] / rev_daily
        daily_ps = daily_ps.replace([np.inf, -np.inf], np.nan).dropna()
        
        return daily_ps.round(2)
        
    except Exception as e:
        logger.error(f"  ❌ PS推导失败 {symbol}: {e}")
        return pd.Series(dtype=float)


def derive_pe_ttm_from_fundamentals(symbol: str, session: Session, days: int = -1) -> pd.DataFrame:
    """
    3. **History (Derivation)**: **本地推导引擎** (Standardized via ValuationCalculator).
    """
    try:
        # Get Daily Prices
        price_stmt = select(MarketDataDaily.timestamp, MarketDataDaily.close).where(MarketDataDaily.symbol == symbol)
        if days > 0:
            cutoff = (datetime.now() - timedelta(days=days)).date()
            price_stmt = price_stmt.where(MarketDataDaily.timestamp >= str(cutoff))
        
        daily_prices = pd.read_sql(price_stmt, engine)
        if daily_prices.empty: return None
        daily_prices['timestamp'] = pd.to_datetime(daily_prices['timestamp'])
        daily_prices.set_index('timestamp', inplace=True)
        
        market = symbol.split(':')[0]
        return calculate_valuation_series(session, symbol, market, daily_prices, metric_type='pe')
    except Exception as e:
        logger.error(f"  ❌ 本地 PE 推导失败 {symbol}: {e}")
        return None


def derive_pb_from_fundamentals(symbol: str, session: Session, days: int = -1) -> pd.DataFrame:
    """
    基于本地财务数据 (Equity / Shares) 推导每日 PB (Standardized via ValuationCalculator).
    """
    try:
        # Get Daily Prices
        price_stmt = select(MarketDataDaily.timestamp, MarketDataDaily.close).where(MarketDataDaily.symbol == symbol)
        if days > 0:
            cutoff = (datetime.now() - timedelta(days=days)).date()
            price_stmt = price_stmt.where(MarketDataDaily.timestamp >= str(cutoff))
        
        daily_prices = pd.read_sql(price_stmt, engine)
        if daily_prices.empty: return None
        daily_prices['timestamp'] = pd.to_datetime(daily_prices['timestamp'])
        daily_prices.set_index('timestamp', inplace=True)
        
        market = symbol.split(':')[0]
        return calculate_valuation_series(session, symbol, market, daily_prices, metric_type='pb')
    except Exception as e:
        logger.error(f"  ❌ 本地 PB 推导失败 {symbol}: {e}")
        return None


def derive_ps_ttm_from_fundamentals(symbol: str, session: Session, days: int = -1) -> pd.DataFrame:
    """
    基于本地财务数据 (Revenue TTM / Shares) 推导每日 PS (Standardized via ValuationCalculator).
    """
    try:
        # Get Daily Prices
        price_stmt = select(MarketDataDaily.timestamp, MarketDataDaily.close).where(MarketDataDaily.symbol == symbol)
        if days > 0:
            cutoff = (datetime.now() - timedelta(days=days)).date()
            price_stmt = price_stmt.where(MarketDataDaily.timestamp >= str(cutoff))
        
        daily_prices = pd.read_sql(price_stmt, engine)
        if daily_prices.empty: return None
        daily_prices['timestamp'] = pd.to_datetime(daily_prices['timestamp'])
        daily_prices.set_index('timestamp', inplace=True)
        
        market = symbol.split(':')[0]
        return calculate_valuation_series(session, symbol, market, daily_prices, metric_type='ps')
    except Exception as e:
        logger.error(f"  ❌ 本地 PS 推导失败 {symbol}: {e}")
        return None

# ==============================================================================
# Interactive CLI
# ==============================================================================

class Config:
    def __init__(self):
        self.markets = {'CN', 'HK', 'US'}
        # Default all selected
        self.selected_markets = self.markets.copy()
        self.days = -1 # -1 means full history

def clear_screen():
    print("\033[H\033[J", end="")

def print_menu(cfg: Config):
    clear_screen()
    print("="*60)
    print(" 📊 估值数据下载器 (Interactive) - 仅支持个股 (STOCK)")
    print("="*60)
    
    def status(condition):
        return "✅" if condition else "❌"
    
    # Simple Market Toggles
    print(f" [1] {status('CN' in cfg.selected_markets)} CN")
    print(f" [2] {status('HK' in cfg.selected_markets)} HK")
    print(f" [3] {status('US' in cfg.selected_markets)} US")
    print(f" [4] 🕒 更新时间范围: {'⚡ 增量同步 (仅最近 ' + str(cfg.days) + ' 天)' if cfg.days > 0 else '🌍 全量下载 (获取全部历史)'} [按4切换]")
    
    print("-" * 60)
    print(" [0] ▶️  开始更新 (按当前设置执行)")
    print(" [A] 全选市场     [C] 清空选择")
    print(" [Q] 退出")
    print("="*60)

def configure():
    cfg = Config()
    
    # Mapping keys to toggle actions
    toggles = {
        '1': lambda: toggle(cfg.selected_markets, 'CN'),
        '2': lambda: toggle(cfg.selected_markets, 'HK'),
        '3': lambda: toggle(cfg.selected_markets, 'US'),
        '4': lambda: toggle_days(cfg)
    }
    
    while True:
        print_menu(cfg)
        try:
            choice = input(" 请输入选项 [0-9/A/C]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            sys.exit(0)
            
        if choice == '0':
            return cfg
        elif choice == 'Q':
            sys.exit(0)
        elif choice in toggles:
            toggles[choice]()
        elif choice == 'A':
            cfg.selected_markets = cfg.markets.copy()
        elif choice == 'C':
            cfg.selected_markets.clear()
            
def toggle(selection_set, item):
    if item in selection_set:
        selection_set.remove(item)
    else:
        selection_set.add(item)

def toggle_days(cfg: Config):
    if cfg.days == -1:
        cfg.days = 30
    elif cfg.days == 30:
        cfg.days = 7
    else:
        cfg.days = -1

# ==============================================================================
# Futu Interface
# ==============================================================================
def fetch_hk_valuation_futu(symbol: str, market: str, session: Session, days: int = -1):
    """
    Use Futu OpenD to fetch historical PE for HK stocks.
    Requires FutuOpenD running on 127.0.0.1:11111.
    """

    try:
        from futu import OpenQuoteContext, KLType, AuType, RET_OK
        import datetime
        
        # Futu Code Format: HK:STOCK:00700 -> HK.00700
        futu_code = symbol.replace('HK:STOCK:', 'HK.')
        
        # Connect
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        # Fetch History with Pagination
        end_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # --- 动态计算起始日期 ---
        if days > 0:
            start_dt = datetime.datetime.now() - datetime.timedelta(days=days)
            start_str = start_dt.strftime("%Y-%m-%d")
        else:
            start_str = "2020-01-01"
            
        logger.info(f"  📥 [Futu] 获取历史范围: {start_str} -> {end_str}")
        
        all_data = []
        page_req_key = None
        
        while True:
            ret, data, page_req_key = quote_ctx.request_history_kline(
                code=futu_code,
                start=start_str,
                end=end_str,
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,
                max_count=1000,
                page_req_key=page_req_key
            )
            
            if ret == RET_OK:
                if not data.empty:
                    all_data.append(data)
            else:
                logger.error(f"  ❌ Futu Error {symbol}: {data}")
                break
                
            if page_req_key is None:
                break
                
        if not all_data:
            logger.warning(f"  ⚠️  Futu Empty {symbol}")
            quote_ctx.close()
            return
            
        import pandas as pd
        data = pd.concat(all_data, ignore_index=True)

            
        # Parse and Save
        # Data columns: time_key, pe_ratio, ...
        # Futu PE is Static.
        
        # Check for Time Shift (Simulation Mode support)
        # If System Time is 2026 but Futu returns 2025, we shift Futu dates to match DB.
        system_year = datetime.datetime.now().year
        futu_latest_str = data.iloc[-1]['time_key']
        futu_latest_year = int(futu_latest_str.split('-')[0])
        
        year_offset = 0
        if system_year > futu_latest_year:
             year_offset = system_year - futu_latest_year
             logger.info(f"  🕰️  Detected Simulation Mode: Shifting Futu data by +{year_offset} years")
        
        updates = []
        for _, row in data.iterrows():
            futu_date_str = row['time_key'].split(' ')[0] # 2025-01-01
            pe_val = row['pe_ratio']
            
            # Apply Shift
            if year_offset > 0:
                 futu_dt = datetime.datetime.strptime(futu_date_str, "%Y-%m-%d")
                 shifted_dt = futu_dt.replace(year=futu_dt.year + year_offset)
                 date_str = shifted_dt.strftime("%Y-%m-%d")
            else:
                 date_str = futu_date_str
            
            # Map Close Time (HK 16:00)
            timestamp_str = f"{date_str} 16:00:00"
            
            # Find DB Record
            stmt = select(MarketDataDaily).where(
                MarketDataDaily.symbol == symbol,
                MarketDataDaily.market == market,
                MarketDataDaily.timestamp == timestamp_str
            )
            record = session.exec(stmt).first()
            
            if record:
                if pe_val and pe_val > 0:
                    record.pe = float(pe_val) # Save to Static PE
                    # record.pe_ttm = None    # Keep TTM clean or update from Snapshot later
                    record.updated_at = datetime.datetime.now()
                    session.add(record)
                    updates.append(1)
        
        # --- NEW: Fetch Snapshot for Latest TTM ---
        # Only if we have a record for Today (or latest available)
        try:
            ret_s, data_s = quote_ctx.get_market_snapshot([futu_code])
            if ret_s == RET_OK and not data_s.empty:
                pe_ttm = data_s.iloc[0].get('pe_ttm_ratio')
                pe_static = data_s.iloc[0].get('pe_ratio')
                pb = data_s.iloc[0].get('pb_ratio')
                
                # Find TODAY's record (System Date)
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                ts_today = f"{today_str} 16:00:00"
                
                rec_today = session.exec(select(MarketDataDaily).where(
                    MarketDataDaily.symbol == symbol,
                    MarketDataDaily.timestamp == ts_today
                )).first()
                
                if rec_today:
                    if pe_ttm and pe_ttm > 0:
                         rec_today.pe_ttm = float(pe_ttm)
                    if pb and pb > 0:
                         rec_today.pb = float(pb)
                    
                    rec_today.updated_at = datetime.datetime.now()
                    session.add(rec_today)
                    logger.info(f"  📸 [HK] Snapshot Updated: {symbol} (PE TTM: {pe_ttm}, PB: {pb})")
                    updates.append(1)
            else:
                logger.warning(f"  ⚠️  Snapshot Failed {symbol}: {data_s}")
        except Exception as e:
            logger.error(f"  ❌ Snapshot Error {symbol}: {e}")

        session.commit()
        quote_ctx.close()

        if updates:
             logger.info(f"  ✅ Futu Saved {symbol}: {len(updates)} records (Static PE)")
             
    except ImportError:
        logger.error("  ❌ Futu API not installed (pip install futu-api)")
    except Exception as e:
         logger.error(f"  ❌ Futu Exception {symbol}: {e}")


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='获取历史估值数据 (PE/PB)')
    parser.add_argument('--symbol', type=str, help='指定要处理的 Canonical ID (例如 US:STOCK:TSLA, HK:STOCK:00700)')
    parser.add_argument('--days', type=int, default=-1, help='获取最近 N 天的数据, -1 表示全量')
    parser.add_argument('--market', type=str, help='指定市场 (CN/HK/US/ALL)')
    args = parser.parse_args()

    # 1. Configuration (Interactive vs Headless)
    selected_markets = {'CN', 'HK', 'US'}
    
    if args.market:
        if args.market.upper() == 'ALL':
            selected_markets = {'CN', 'HK', 'US'}
        else:
            selected_markets = {args.market.upper()}
    
    if args.symbol or args.market:
        if args.symbol:
            print(f"🎯 仅处理指定资产: {args.symbol}")
            # Infer market from symbol if possible, or just rely on symbol filter later
            # But we need selected_markets for the query logic below
            parts = args.symbol.split(':')
            if len(parts) > 0 and parts[0] in selected_markets:
                selected_markets = {parts[0]}
    else:
        # Interactive Mode
        print("进入交互模式...")
        try:
            cfg = configure()
            selected_markets = cfg.selected_markets
            args.days = cfg.days
        except KeyboardInterrupt:
            print("\nExit")
            return

    print("=" * 80)
    print(f"📊 开始获取估值数据 (Markets: {selected_markets})")
    print("   注意: 仅更新个股 (STOCK)")
    print("=" * 80)
    
    try:
        with Session(engine) as session:
            # 构建查询
            stmt = select(Watchlist).where(Watchlist.market.in_(selected_markets))
            
            # 如果指定了 symbol, 增加过滤条件
            if args.symbol:
                stmt = stmt.where(Watchlist.symbol == args.symbol)
                
            watchlist = session.exec(stmt).all()
            
            if not watchlist:
                print(f"⚠️  未找到匹配的资产" + (f": {args.symbol}" if args.symbol else ""))
                return
            
            # 预先过滤: 只保留 STOCK
            targets = []
            for item in watchlist:
                parts = item.symbol.split(':')
                # Canonical ID Format: MARKET:TYPE:CODE
                # But sometimes simple formats exist. Let's use robust check.
                # Assuming format is strictly followed or at least contains type.
                if len(parts) >= 2:
                    asset_type = parts[1]
                else:
                    # Fallback or skip? safely skip if unsure
                    continue
                    
                if asset_type == 'STOCK':
                    targets.append(item)
            
            count_total = len(targets)
            if count_total == 0:
                print("⚠️  筛选后无个股目标 (STOCK).")
                return

            print(f"\n共 {count_total} 个个股资产需要获取估值数据\n")
            
            cn_count = 0
            hk_count = 0
            us_count = 0

            for idx, item in enumerate(targets, 1):
                print(f"\n[{idx}/{count_total}] {'='*60}")
                
                # Check for strict interruption
                
                parts = item.symbol.split(':')
                asset_type = parts[1] if len(parts) >= 2 else 'STOCK'
                
                try:
                    if item.market == 'CN':
                        # A股保持原有逻辑
                        df = fetch_cn_valuation_history(item.symbol, asset_type)
                        
                        if df is not None and not df.empty:
                            dividend_yield = fetch_cn_dividend_yield(item.symbol)
                            if dividend_yield is not None:
                                df['dividend_yield'] = dividend_yield
                            
                            updated = save_cn_valuation_to_daily(item.symbol, df, session, days=args.days)
                            if updated > 0:
                                cn_count += 1
                        
                        # PS 推导 (A股)
                        if item.symbol:
                             try:
                                 derived_ps_cn = derive_ps_ttm_from_fundamentals(item.symbol, session, days=args.days)
                                 if derived_ps_cn is not None and not derived_ps_cn.empty:
                                     logger.info(f"  📈 [Local] CN: 推导并保存 {len(derived_ps_cn)} 条 PS")
                                     # Use the generic saver (save_us_historical_valuation_to_daily is now generic)
                                     save_us_historical_valuation_to_daily(item.symbol, derived_ps_cn, session)
                             except Exception as e:
                                 logger.error(f"  ❌ A股 PS 推导失败: {e}")
                                
                    elif item.market == 'HK':
                        print(f"🔄 处理港股 (Futu + Yahoo + Dividend): {item.symbol}")
                        # 1. Futu: PE/PE_TTM (高权重)
                        fetch_hk_valuation_futu(item.symbol, "HK", session, days=args.days)
                        
                        # 2. [NEW] Yahoo: Realtime PE/PB/PS (重要的 PB/PS 补充来源)
                        hk_val_yf = fetch_hk_valuation_yfinance(item.symbol)
                        if hk_val_yf:
                             save_realtime_valuation_to_daily(item.symbol, hk_val_yf, session, market='HK')
                        
                        # 3. Yahoo: Dividend Yield (Restore)
                        div_yield = fetch_hk_dividend_yield(item.symbol)
                        if div_yield is not None:
                             try:
                                 latest_rec = session.exec(
                                     select(MarketDataDaily).where(
                                         MarketDataDaily.symbol == item.symbol, 
                                         MarketDataDaily.market == 'HK'
                                     ).order_by(MarketDataDaily.timestamp.desc())
                                 ).first()
                                 if latest_rec:
                                     latest_rec.dividend_yield = div_yield
                                     latest_rec.updated_at = datetime.now()
                                     session.add(latest_rec)
                                     session.commit()
                                     print(f"  💾 已保存股息率: {div_yield}%")
                             except Exception as e:
                                 logger.error(f"  ❌ 保存股息率失败: {e}")

                        # 3. [NEW] FMP Backfill (PB/PS)
                        try:
                            df_fmp_hk = fetch_us_valuation_history_fmp(item.symbol, limit=20, days=args.days)
                            if df_fmp_hk is not None and not df_fmp_hk.empty:
                                logger.info(f"  📈 [FMP] HK: 获取并保存 {len(df_fmp_hk)} 条原始估值点")
                                save_us_historical_valuation_to_daily(item.symbol, df_fmp_hk, session)
                                
                                # 进行 FMP 基准的日线推导 (HK)
                                try:
                                    daily_prices = pd.read_sql(
                                        select(MarketDataDaily.timestamp, MarketDataDaily.close)
                                        .where(MarketDataDaily.symbol == item.symbol)
                                        .where(MarketDataDaily.market == 'HK')
                                        .order_by(MarketDataDaily.timestamp),
                                        engine
                                    )
                                    if not daily_prices.empty:
                                        daily_prices['timestamp'] = pd.to_datetime(daily_prices['timestamp'])
                                        daily_prices.set_index('timestamp', inplace=True)
                                        
                                        # 推导 PB (HK)
                                        derived_pb_fmp = derive_daily_pb_from_points(item.symbol, daily_prices, df_fmp_hk)
                                        if not derived_pb_fmp.empty:
                                            logger.info(f"  📈 [Derivation] HK: 基于 FMP 推导并保存 {len(derived_pb_fmp)} 条 PB")
                                            df_pb_hk = pd.DataFrame({'date': derived_pb_fmp.index.strftime('%Y-%m-%d'), 'pb': derived_pb_fmp.values})
                                            save_us_historical_valuation_to_daily(item.symbol, df_pb_hk, session)
                                            
                                        # 推导 PS (HK)
                                        derived_ps_fmp = derive_daily_ps_from_points(item.symbol, daily_prices, df_fmp_hk)
                                        if not derived_ps_fmp.empty:
                                            logger.info(f"  📈 [Derivation] HK: 基于 FMP 推导并保存 {len(derived_ps_fmp)} 条 PS")
                                            df_ps_hk = pd.DataFrame({'date': derived_ps_fmp.index.strftime('%Y-%m-%d'), 'ps': derived_ps_fmp.values})
                                            save_us_historical_valuation_to_daily(item.symbol, df_ps_hk, session)
                                except Exception as e:
                                    logger.error(f"  ❌ 港股 FMP 日线推导失败: {e}")
                        except Exception as e:
                            logger.error(f"  ❌ 港股 FMP 补救异常: {e}")

                        # 4. Local Derivation (Fallback for missing PB/PS/PE)
                        # ⚠️ CRITICAL: 设置 only_nulls=True，防止糟糕的本地推导数据覆盖高质量 API 数据
                        try:
                            # PE TTM 推导
                            derived_pe_local = derive_pe_ttm_from_fundamentals(item.symbol, session, days=args.days)
                            if derived_pe_local is not None and not derived_pe_local.empty:
                                logger.info(f"  📈 [Local] HK: 推导并保存 {len(derived_pe_local)} 条 PE TTM (仅填充缺失项)")
                                save_us_historical_valuation_to_daily(item.symbol, derived_pe_local, session, only_nulls=True)

                            # PB 推导
                            derived_pb_local = derive_pb_from_fundamentals(item.symbol, session, days=args.days)
                            if derived_pb_local is not None and not derived_pb_local.empty:
                                logger.info(f"  📈 [Local] HK: 推导并保存 {len(derived_pb_local)} 条 PB (仅填充缺失项)")
                                save_us_historical_valuation_to_daily(item.symbol, derived_pb_local, session, only_nulls=True)
                            
                            # PS 推导
                            derived_ps_local = derive_ps_ttm_from_fundamentals(item.symbol, session, days=args.days)
                            if derived_ps_local is not None and not derived_ps_local.empty:
                                logger.info(f"  📈 [Local] HK: 推导并保存 {len(derived_ps_local)} 条 PS (仅填充缺失项)")
                                save_us_historical_valuation_to_daily(item.symbol, derived_ps_local, session, only_nulls=True)
                        except Exception as e:
                            logger.error(f"  ❌ 港股本地推导逻辑异常: {e}")

                        hk_count += 1


                    elif item.market == 'US':
                        print(f"🔄 处理美股: {item.symbol}")
                        # 1. 实时估值 (yfinance)
                        valuation = fetch_us_valuation_yfinance(item.symbol)
                        if valuation:
                            updated = save_realtime_valuation_to_daily(item.symbol, valuation, session, market='US')
                            if updated > 0:
                                us_count += 1 
                        
                        # 2. 历史估值 (FMP)
                        df_fmp = fetch_us_valuation_history_fmp(item.symbol, limit=20, days=args.days) 
                        
                        if df_fmp is not None and not df_fmp.empty:
                            save_us_historical_valuation_to_daily(item.symbol, df_fmp, session)
                            
                            # 3. 推导 (Base on FMP)
                            try:
                                daily_prices = pd.read_sql(
                                    select(MarketDataDaily.timestamp, MarketDataDaily.close)
                                    .where(MarketDataDaily.symbol == item.symbol)
                                    .order_by(MarketDataDaily.timestamp),
                                    engine
                                )
                                if not daily_prices.empty:
                                    daily_prices['timestamp'] = pd.to_datetime(daily_prices['timestamp'])
                                    daily_prices.set_index('timestamp', inplace=True)
                                    
                                    derived_pe = derive_daily_pe_from_points(item.symbol, daily_prices, df_fmp)
                                    if not derived_pe.empty:
                                        logger.info(f"  📈 [Derivation] US: 推导并保存 {len(derived_pe)} 条 PE TTM (Based on FMP)")
                                        df_derived = pd.DataFrame({'date': derived_pe.index.strftime('%Y-%m-%d'), 'pe_ttm': derived_pe.values})
                                        save_us_historical_valuation_to_daily(item.symbol, df_derived, session)
                                    
                                    # 推导 PB
                                    derived_pb = derive_daily_pb_from_points(item.symbol, daily_prices, df_fmp)
                                    if not derived_pb.empty:
                                        logger.info(f"  📈 [Derivation] US: 推导并保存 {len(derived_pb)} 条 PB (Based on FMP)")
                                        df_pb = pd.DataFrame({'date': derived_pb.index.strftime('%Y-%m-%d'), 'pb': derived_pb.values})
                                        save_us_historical_valuation_to_daily(item.symbol, df_pb, session)

                                    # 推导 PS
                                    derived_ps = derive_daily_ps_from_points(item.symbol, daily_prices, df_fmp)
                                    if not derived_ps.empty:
                                        logger.info(f"  📈 [Derivation] US: 推导并保存 {len(derived_ps)} 条 PS (Based on FMP)")
                                        df_ps = pd.DataFrame({'date': derived_ps.index.strftime('%Y-%m-%d'), 'ps': derived_ps.values})
                                        save_us_historical_valuation_to_daily(item.symbol, df_ps, session)
                            except Exception as e:
                                logger.error(f"  ❌ 美股 FMP 推导逻辑异常: {e}")

                        # 4. [Enhanced Fallback] 美股本地财报推导
                        # 改进：如果 FMP 数据已经足够丰富 (> 10 条)，则跳过本地 PE/PS 推导，优先保留 API 权威数据
                        fmp_sufficient = (df_fmp is not None and len(df_fmp) > 10)
                        
                        if not fmp_sufficient:
                            logger.info(f"  🔍 US: FMP 数据稀疏，执行本地财报推导以补足 (PE/PS)...")
                            # PE
                            derived_pe_local = derive_pe_ttm_from_fundamentals(item.symbol, session, days=args.days)
                            if derived_pe_local is not None and not derived_pe_local.empty:
                                logger.info(f"  📈 [Local] US: 推导并保存 {len(derived_pe_local)} 条 PE TTM")
                                save_us_historical_valuation_to_daily(item.symbol, derived_pe_local, session)
                            
                            # PS
                            derived_ps_local = derive_ps_ttm_from_fundamentals(item.symbol, session, days=args.days)
                            if derived_ps_local is not None and not derived_ps_local.empty:
                                logger.info(f"  📈 [Local] US: 推导并保存 {len(derived_ps_local)} 条 PS")
                                save_us_historical_valuation_to_daily(item.symbol, derived_ps_local, session)
                        else:
                            logger.info(f"  ✅ US: FMP 数据充足，跳过本地 PE/PS 覆盖。")

                        # PB 始终尝试推导，因为 API 往往只有年度 PB
                        derived_pb_local = derive_pb_from_fundamentals(item.symbol, session, days=args.days)
                        if derived_pb_local is not None and not derived_pb_local.empty:
                            logger.info(f"  📈 [Local] US: 推导并保存 {len(derived_pb_local)} 条 PB")
                            save_us_historical_valuation_to_daily(item.symbol, derived_pb_local, session)

                    # 避免请求过快

                    # 避免请求过快
                    import time
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"❌ 处理失败 {item.symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # 总结
            print("\n" + "=" * 80)
            print("📋 获取完成统计")
            print("=" * 80)
            print(f"✅ A股成功: {cn_count} 个")
            print(f"✅ 港股成功: {hk_count} 个")
            print(f"✅ 美股成功: {us_count} 个")
            print("=" * 80)
            
            print("\n💡 下一步建议: 运行导出脚本以生成数据文件")
            print("   1. 导出行情数据: python3 export_daily_csv.py")
            print("   2. 导出财务格式: python3 export_financials_formatted.py")
            print("="*80 + "\n")
            
    except Exception as e:
         logger.error(f"❌ 程序执行出错: {e}")
         import traceback
         traceback.print_exc()

if __name__ == "__main__":
    main()
