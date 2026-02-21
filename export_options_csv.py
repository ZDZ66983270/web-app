#!/usr/bin/env python3
"""
期权数据导出脚本 - export_options_csv.py
==============================================================================

功能:
1. 从数据库导出未过期的期权数据
2. 按市场分组导出
3. 包含完整的希腊字母和定价信息
4. 自动过滤过期期权

使用方法:
    python3 export_options_csv.py
    python3 export_options_csv.py --market US
    python3 export_options_csv.py --market HK
"""

import argparse
import os
from datetime import datetime
import pandas as pd
from sqlmodel import Session, select
from backend.database import engine
from backend.option_models import OptionData
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_options_data(market=None, output_dir='outputs'):
    """
    导出期权数据到CSV
    
    参数:
        market: 市场过滤 (US/HK/None表示全部)
        output_dir: 输出目录
    """
    logger.info("="*60)
    logger.info("期权数据导出任务启动")
    logger.info("="*60)
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    with Session(engine) as session:
        # 构建查询 - 只查询未过期的期权
        stmt = select(OptionData).where(OptionData.expiry_date >= today)
        
        if market:
            stmt = stmt.where(OptionData.market == market)
        
        # 按到期日和执行价排序
        stmt = stmt.order_by(
            OptionData.symbol,
            OptionData.expiry_date,
            OptionData.strike
        )
        
        options = session.exec(stmt).all()
        
        if not options:
            logger.warning("❌ 没有找到未过期的期权数据")
            return
        
        logger.info(f"📊 找到 {len(options)} 条未过期期权数据")
        
        # 转换为DataFrame
        data = []
        for opt in options:
            # 计算价值状态标签
            if opt.moneyness > 0.02:
                itm_status = "价内(ITM)"
            elif opt.moneyness < -0.02:
                itm_status = "价外(OTM)"
            else:
                itm_status = "平值(ATM)"
            
            # 计算理论价格与市场价格的偏差
            price_diff = None
            price_diff_pct = None
            if opt.theoretical_price:
                price_diff = opt.last_price - opt.theoretical_price
                price_diff_pct = (price_diff / opt.theoretical_price * 100) if opt.theoretical_price > 0 else None
            
            data.append({
                # 基础信息
                'symbol': opt.symbol,
                'market': opt.market,
                'underlying_price': opt.underlying_price,
                'currency': opt.currency,
                
                # 期权合约信息
                'option_symbol': opt.option_symbol,
                'strike': opt.strike,
                'expiry_date': opt.expiry_date,
                'days_to_expiry': opt.days_to_expiry,
                'moneyness_%': opt.moneyness * 100,
                'itm_status': itm_status,
                
                # 市场价格
                'last_price': opt.last_price,
                'bid': opt.bid,
                'ask': opt.ask,
                'bid_ask_spread': opt.ask - opt.bid if opt.ask and opt.bid else None,
                'volume': opt.volume,
                'open_interest': opt.open_interest,
                
                # 希腊字母
                'implied_volatility_%': opt.implied_volatility * 100 if opt.implied_volatility else None,
                'delta': opt.delta,
                'gamma': opt.gamma,
                'theta': opt.theta,
                'vega': opt.vega,
                'rho': opt.rho,
                
                # 理论定价
                'theoretical_price': opt.theoretical_price,
                'price_diff': price_diff,
                'price_diff_%': price_diff_pct,
                
                # 元数据
                'data_source': opt.data_source,
                'updated_at': opt.updated_at.strftime('%Y-%m-%d %H:%M:%S') if opt.updated_at else None
            })
        
        df = pd.DataFrame(data)
        
        # 按市场分组统计
        logger.info("\n市场分布:")
        for mkt in df['market'].unique():
            count = len(df[df['market'] == mkt])
            symbols = df[df['market'] == mkt]['symbol'].nunique()
            logger.info(f"  {mkt}: {count} 条期权, {symbols} 只股票")
        
        # 导出全部数据
        output_file = os.path.join(output_dir, f"options_data_all_{today}.csv")
        
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"\n✅ 全部数据已导出到: {output_file}")
        
        # 生成汇总报告
        generate_summary_report(df, output_dir, today)

def generate_summary_report(df, output_dir, today):
    """生成期权数据汇总报告"""
    
    summary_lines = []
    summary_lines.append("="*60)
    summary_lines.append("期权数据汇总报告")
    summary_lines.append("="*60)
    summary_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"数据日期: {today}")
    summary_lines.append("")
    
    # 总体统计
    summary_lines.append("【总体统计】")
    summary_lines.append(f"  总期权数: {len(df)}")
    summary_lines.append(f"  涉及股票: {df['symbol'].nunique()}")
    summary_lines.append(f"  市场数量: {df['market'].nunique()}")
    summary_lines.append("")
    
    # 按市场统计
    summary_lines.append("【市场分布】")
    for market in sorted(df['market'].unique()):
        mkt_df = df[df['market'] == market]
        summary_lines.append(f"  {market}:")
        summary_lines.append(f"    期权数: {len(mkt_df)}")
        summary_lines.append(f"    股票数: {mkt_df['symbol'].nunique()}")
        summary_lines.append(f"    平均IV: {mkt_df['implied_volatility_%'].mean():.2f}%")
        summary_lines.append("")
    
    # 按到期月份统计
    summary_lines.append("【到期分布】")
    df['expiry_month'] = pd.to_datetime(df['expiry_date']).dt.to_period('M')
    for month in sorted(df['expiry_month'].unique()):
        month_df = df[df['expiry_month'] == month]
        summary_lines.append(f"  {month}:")
        summary_lines.append(f"    期权数: {len(month_df)}")
        summary_lines.append(f"    平均天数: {month_df['days_to_expiry'].mean():.0f} 天")
        summary_lines.append("")
    
    # 价值状态分布
    summary_lines.append("【价值状态分布】")
    for status in ['价内(ITM)', '平值(ATM)', '价外(OTM)']:
        count = len(df[df['itm_status'] == status])
        pct = count / len(df) * 100 if len(df) > 0 else 0
        summary_lines.append(f"  {status}: {count} ({pct:.1f}%)")
    summary_lines.append("")
    
    # Top 10 高IV期权
    summary_lines.append("【Top 10 高隐含波动率期权】")
    top_iv = df.nlargest(10, 'implied_volatility_%')[['symbol', 'strike', 'expiry_date', 'implied_volatility_%', 'last_price']]
    for idx, row in top_iv.iterrows():
        summary_lines.append(f"  {row['symbol']} ${row['strike']:.0f} {row['expiry_date']} - IV {row['implied_volatility_%']:.1f}% - ${row['last_price']:.2f}")
    summary_lines.append("")
    
    summary_lines.append("="*60)
    
    # 保存报告
    report_file = os.path.join(output_dir, f"options_summary_{today}.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines))
    
    # 同时打印到控制台
    logger.info("\n" + '\n'.join(summary_lines))
    logger.info(f"\n📄 汇总报告已保存到: {report_file}")

def main():
    parser = argparse.ArgumentParser(description='导出期权数据到CSV')
    parser.add_argument('--market', type=str, choices=['US', 'HK'],
                       help='市场过滤 (US/HK，不指定则导出全部)')
    parser.add_argument('--output', type=str, default='outputs',
                       help='输出目录 (默认: outputs)')
    
    args = parser.parse_args()
    
    export_options_data(market=args.market, output_dir=args.output)

if __name__ == "__main__":
    main()
