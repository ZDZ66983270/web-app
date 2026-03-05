#!/usr/bin/env python3
"""
backfill_pb_ps_history.py
===========================
回填个股历史 PB 和 PS 日线数据。

策略（按优先级）:
  1. FMP /stable/ratios annual (limit=5)  → 获取 BVPS & RPS 每股锚点（最近5年，年度）
     Daily PB = close / BVPS_forward_filled
     Daily PS = close / RPS_forward_filled

  2. 本地 financialfundamentals（equity + revenue 除以 yfinance 股数）- 备用

  锚点 forward-fill 到每日，使得历史每一天的 PB/PS 都基于最新可用财报。
  只填充现有记录中 pb/ps 为 NULL 的字段，不覆盖已有值。

用法:
  python3 backfill_pb_ps_history.py                    # 回填全部个股
  python3 backfill_pb_ps_history.py --symbol AAPL      # 单只
  python3 backfill_pb_ps_history.py --market US        # 某市场
  python3 backfill_pb_ps_history.py --dry-run          # 预览不写入
  python3 backfill_pb_ps_history.py --check            # 统计当前覆盖情况
"""

import argparse
import sys
import time
import requests
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).parent
DB_PATH     = BASE_DIR / "backend" / "database.db"
FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"

# ADR 修正: 1 ADR = N 普通股
ADR_RATIO_MAP = {
    "US:STOCK:TSM": 5.0,
}

# FMP annual limit（免费账户每次最多5条，对应近5年年报）
FMP_ANNUAL_LIMIT = 5


# ─── FMP: 获取年度 BVPS / RPS ─────────────────────────────────────────────
def fetch_fmp_bvps_rps(symbol: str) -> pd.DataFrame | None:
    """
    从 FMP /stable/ratios?annual&limit=5 获取近5年年报的 BVPS 和 RPS。
    返回 DataFrame: index=date, columns=[bvps, rps]
    """
    code = symbol.split(":")[-1]
    if "HK:STOCK:" in symbol:
        code = f"{code}.HK"
    elif "CN:STOCK:" in symbol:
        code = f"{code}.SS" if code.startswith("6") else f"{code}.SZ"

    url = (f"https://financialmodelingprep.com/stable/ratios"
           f"?symbol={code}&period=annual&limit={FMP_ANNUAL_LIMIT}&apikey={FMP_API_KEY}")
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            print(f"  ⚠️  FMP HTTP {resp.status_code}: {resp.text[:100]}")
            return None
        data = resp.json()
        if not data or isinstance(data, dict):
            return None

        adr = ADR_RATIO_MAP.get(symbol, 1.0)
        records = []
        for item in data:
            bvps = item.get("bookValuePerShare")
            rps  = item.get("revenuePerShare")
            # ADR 修正: ADR_price = ordinary_share_price * adr_ratio
            # BVPS_ADR = BVPS_ordinary * adr_ratio
            if bvps and adr != 1.0:
                bvps = bvps * adr
            if rps and adr != 1.0:
                rps = rps * adr
            records.append({
                "date": pd.to_datetime(item.get("date")),
                "bvps": bvps,
                "rps":  rps,
            })

        df = pd.DataFrame(records).dropna(subset=["date"]).sort_values("date")
        df = df.set_index("date")
        print(f"  ✅ FMP annual: {len(df)}条  BVPS={df['bvps'].notna().sum()}  RPS={df['rps'].notna().sum()}")
        return df

    except Exception as e:
        print(f"  ❌ FMP 请求失败 {code}: {e}")
        return None


# ─── 推导日线 PB / PS ─────────────────────────────────────────────────────
def derive_daily(
    daily_prices: pd.DataFrame,  # index=date, columns=['close']
    anchors: pd.Series,          # index=date, value=BVPS or RPS
) -> pd.Series:
    """
    forward-fill 锚点（BVPS/RPS）到每个交易日，再算 ratio = close / anchor。
    """
    if anchors.dropna().empty or daily_prices.empty:
        return pd.Series(dtype=float)

    daily_idx = daily_prices.index

    # 合并锚点和日线索引，forward-fill
    merged_idx   = daily_idx.union(anchors.index).sort_values()
    anchor_ff    = anchors.reindex(merged_idx).ffill()
    anchor_daily = anchor_ff.reindex(daily_idx)

    ratio = (daily_prices["close"] / anchor_daily).replace([np.inf, -np.inf], np.nan).dropna()
    return ratio.round(4)


# ─── 读日线价格 ──────────────────────────────────────────────────────────
def load_daily_prices(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT timestamp, close FROM marketdatadaily WHERE symbol=? ORDER BY timestamp",
        conn, params=(symbol,)
    )
    df["date"] = pd.to_datetime(df["timestamp"].str[:10])
    df = df.dropna(subset=["date", "close"]).set_index("date")[["close"]]
    df = df[~df.index.duplicated(keep="first")]
    return df


# ─── 写回 DB (only_nulls) ─────────────────────────────────────────────────
def write_to_db(
    conn: sqlite3.Connection,
    symbol: str,
    pb_series: pd.Series,
    ps_series: pd.Series,
    dry_run: bool = False,
) -> dict:
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pb_written = ps_written = total_eligible = 0

    all_dates = sorted(set(pb_series.index.tolist()) | set(ps_series.index.tolist()))

    for d in all_dates:
        date_prefix = d.strftime("%Y-%m-%d")
        pb_val = float(pb_series[d]) if d in pb_series.index and pd.notna(pb_series[d]) else None
        ps_val = float(ps_series[d]) if d in ps_series.index and pd.notna(ps_series[d]) else None

        cur.execute(
            "SELECT id, pb, ps FROM marketdatadaily WHERE symbol=? AND timestamp LIKE ?",
            (symbol, f"{date_prefix}%"),
        )
        rows = cur.fetchall()
        for row_id, cur_pb, cur_ps in rows:
            total_eligible += 1
            updates = {}
            if pb_val is not None and cur_pb is None:
                updates["pb"] = pb_val
                pb_written += 1
            if ps_val is not None and cur_ps is None:
                updates["ps"] = ps_val
                ps_written += 1
            if updates and not dry_run:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                cur.execute(
                    f"UPDATE marketdatadaily SET {set_clause}, updated_at=? WHERE id=?",
                    list(updates.values()) + [now, row_id]
                )

    if not dry_run and (pb_written + ps_written) > 0:
        conn.commit()

    return {"pb_written": pb_written, "ps_written": ps_written, "eligible": total_eligible}


# ─── 单只主流程 ───────────────────────────────────────────────────────────
def backfill_symbol(conn: sqlite3.Connection, symbol: str, dry_run: bool = False) -> dict:
    print(f"\n{'─'*60}\n  [{symbol}]")

    daily = load_daily_prices(conn, symbol)
    if daily.empty:
        print("  ⏭️  无日线数据，跳过")
        return {}

    print(f"  📅 日线: {daily.index.min().date()} ~ {daily.index.max().date()} ({len(daily)}条)")

    # FMP 年度锚点
    anchors = fetch_fmp_bvps_rps(symbol)
    time.sleep(0.3)  # rate limit

    pb_series = ps_series = pd.Series(dtype=float)

    if anchors is not None and not anchors.empty:
        bvps = anchors["bvps"].dropna()
        rps  = anchors["rps"].dropna()
        if not bvps.empty:
            pb_series = derive_daily(daily, bvps)
        if not rps.empty:
            ps_series = derive_daily(daily, rps)

    if pb_series.empty and ps_series.empty:
        print("  ⏭️  推导结果为空，跳过")
        return {}

    print(f"  📐 推导  PB={len(pb_series)}条  PS={len(ps_series)}条")

    result = write_to_db(conn, symbol, pb_series, ps_series, dry_run=dry_run)
    tag = "[DRY-RUN] " if dry_run else ""
    print(f"  💾 {tag}写入  PB={result['pb_written']}条  PS={result['ps_written']}条  "
          f"(总{result['eligible']}条日线)")
    return result


# ─── 入口 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="回填个股历史 PB/PS")
    parser.add_argument("--symbol",  help="只处理指定代码 (AAPL 或 US:STOCK:AAPL)")
    parser.add_argument("--market",  choices=["US", "HK", "CN"], help="限定市场")
    parser.add_argument("--dry-run", action="store_true", help="不写入 DB，仅预览")
    parser.add_argument("--check",   action="store_true", help="只统计当前 PB/PS 覆盖")
    parser.add_argument("--sleep",   type=float, default=1.2, help="每只请求间隔秒 (默认 1.2)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))

    # ── check 模式 ─────────────────────────────────────────────────────
    if args.check:
        print(f"{'Symbol':<30} {'Total':>7} {'有PB':>7} {'PB%':>5} {'有PS':>7} {'PS%':>5}")
        print("─" * 62)
        cur = conn.cursor()
        cur.execute("SELECT symbol FROM watchlist WHERE symbol LIKE '%:STOCK:%' ORDER BY market, symbol")
        for (sym,) in cur.fetchall():
            cur.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN pb>0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN ps>0 THEN 1 ELSE 0 END)
                FROM marketdatadaily WHERE symbol=?
            """, (sym,))
            total, pb_cnt, ps_cnt = cur.fetchone()
            total  = total  or 0
            pb_cnt = pb_cnt or 0
            ps_cnt = ps_cnt or 0
            pb_pct = f"{pb_cnt/total*100:.0f}%" if total else "--"
            ps_pct = f"{ps_cnt/total*100:.0f}%" if total else "--"
            print(f"{sym:<30} {total:>7} {pb_cnt:>7} {pb_pct:>5} {ps_cnt:>7} {ps_pct:>5}")
        conn.close()
        return

    # ── 生成股票列表 ───────────────────────────────────────────────────
    query  = "SELECT symbol FROM watchlist WHERE symbol LIKE '%:STOCK:%'"
    params = []
    if args.market:
        query += " AND market=?"
        params.append(args.market)
    if args.symbol:
        s = args.symbol.strip()
        if ":" not in s:
            query += " AND symbol LIKE ?"
            params.append(f"%:{s}")
        else:
            query += " AND symbol=?"
            params.append(s)
    query += " ORDER BY market, symbol"

    cur = conn.cursor()
    cur.execute(query, params)
    symbols = [r[0] for r in cur.fetchall()]

    if not symbols:
        print("未找到匹配的股票")
        sys.exit(0)

    print(f"📋 共 {len(symbols)} 只个股待处理")
    if args.dry_run:
        print("⚠️  DRY-RUN 模式，不写入 DB")

    total_pb = total_ps = 0
    for i, sym in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}]", end="")
        r = backfill_symbol(conn, sym, dry_run=args.dry_run)
        total_pb += r.get("pb_written", 0)
        total_ps += r.get("ps_written", 0)
        if i < len(symbols):
            time.sleep(args.sleep)

    conn.close()
    print(f"\n\n{'='*60}")
    print(f"✅ 完成！总计写入  PB={total_pb}条  PS={total_ps}条")


if __name__ == "__main__":
    main()
