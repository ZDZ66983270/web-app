#!/usr/bin/env python3
"""
期权希腊字母计算测试脚本
使用 yfinance 获取期权数据，通过 mibian 库反推计算希腊字母
"""

import yfinance as yf
import mibian
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def calculate_days_to_expiry(expiry_date_str):
    """计算距离到期日的天数"""
    expiry = datetime.strptime(expiry_date_str, '%Y-%m-%d')
    today = datetime.now()
    days = (expiry - today).days
    return max(1, days)  # 至少返回1天

def get_option_greeks(ticker_symbol, risk_free_rate=0.045):
    """
    获取期权数据并计算希腊字母
    
    参数:
        ticker_symbol: 股票代码 (如 'AAPL')
        risk_free_rate: 无风险利率 (默认4.5%)
    """
    print(f"\n{'='*60}")
    print(f"正在分析 {ticker_symbol} 的期权希腊字母...")
    print(f"{'='*60}\n")
    
    # 1. 获取标的资产信息
    stock = yf.Ticker(ticker_symbol)
    
    # 获取当前股价
    try:
        current_price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice')
        if not current_price:
            # 如果info中没有，尝试从历史数据获取最新价格
            hist = stock.history(period='1d')
            current_price = hist['Close'].iloc[-1] if not hist.empty else None
        
        if not current_price:
            print("❌ 无法获取当前股价")
            return None
            
        print(f"📊 标的资产: {ticker_symbol}")
        print(f"💰 当前股价: ${current_price:.2f}")
        
    except Exception as e:
        print(f"❌ 获取股价失败: {e}")
        return None
    
    # 2. 获取期权到期日列表
    try:
        expiry_dates = stock.options
        if not expiry_dates:
            print("❌ 该股票没有可用的期权数据")
            return None
        
        print(f"\n📅 可用的期权到期日: {len(expiry_dates)} 个")
        print(f"   最近到期: {expiry_dates[0]}")
        print(f"   最远到期: {expiry_dates[-1]}")
        
        # 选择最近的到期日
        selected_expiry = expiry_dates[0]
        days_to_expiry = calculate_days_to_expiry(selected_expiry)
        print(f"\n✅ 选择到期日: {selected_expiry} (距今 {days_to_expiry} 天)")
        
    except Exception as e:
        print(f"❌ 获取期权到期日失败: {e}")
        return None
    
    # 3. 获取期权链数据
    try:
        option_chain = stock.option_chain(selected_expiry)
        calls = option_chain.calls
        puts = option_chain.puts
        
        print(f"\n📈 看涨期权 (Calls): {len(calls)} 个")
        print(f"📉 看跌期权 (Puts): {len(puts)} 个")
        
    except Exception as e:
        print(f"❌ 获取期权链失败: {e}")
        return None
    
    # 4. 选择接近平值的期权进行分析
    results = []
    
    # 找到最接近当前价格的执行价
    calls['distance'] = abs(calls['strike'] - current_price)
    atm_call = calls.loc[calls['distance'].idxmin()]
    
    puts['distance'] = abs(puts['strike'] - current_price)
    atm_put = puts.loc[puts['distance'].idxmin()]
    
    print(f"\n{'='*60}")
    print("🎯 平值期权分析")
    print(f"{'='*60}")
    
    # 分析看涨期权
    print(f"\n【看涨期权 (Call)】")
    print(f"  执行价: ${atm_call['strike']:.2f}")
    print(f"  最新价: ${atm_call['lastPrice']:.2f}")
    print(f"  买价: ${atm_call['bid']:.2f}")
    print(f"  卖价: ${atm_call['ask']:.2f}")
    print(f"  隐含波动率: {atm_call['impliedVolatility']*100:.2f}%")
    
    # 使用 mibian 计算看涨期权希腊字母
    if atm_call['impliedVolatility'] > 0:
        call_greeks = mibian.BS(
            [current_price,                          # 标的价格
             atm_call['strike'],                     # 执行价
             risk_free_rate * 100,                   # 无风险利率 (百分比)
             days_to_expiry],                        # 到期天数
            volatility=atm_call['impliedVolatility'] * 100  # 隐含波动率 (百分比)
        )
        
        print(f"\n  🔢 希腊字母:")
        print(f"     Delta:   {call_greeks.callDelta:.4f}  (价格变动1美元，期权价格变动)")
        print(f"     Gamma:   {call_greeks.gamma:.4f}  (Delta的变化率)")
        print(f"     Theta:   {call_greeks.callTheta:.4f}  (每天时间价值衰减)")
        print(f"     Vega:    {call_greeks.vega:.4f}  (波动率变动1%的影响)")
        print(f"     Rho:     {call_greeks.callRho:.4f}  (利率变动1%的影响)")
        
        # 理论价格
        print(f"\n  💡 理论价格: ${call_greeks.callPrice:.2f}")
        print(f"     市场价格: ${atm_call['lastPrice']:.2f}")
        print(f"     价差: ${abs(call_greeks.callPrice - atm_call['lastPrice']):.2f}")
        
        results.append({
            'Type': 'Call',
            'Strike': atm_call['strike'],
            'Market_Price': atm_call['lastPrice'],
            'Theoretical_Price': call_greeks.callPrice,
            'IV': atm_call['impliedVolatility'] * 100,
            'Delta': call_greeks.callDelta,
            'Gamma': call_greeks.gamma,
            'Theta': call_greeks.callTheta,
            'Vega': call_greeks.vega,
            'Rho': call_greeks.callRho
        })
    
    # 分析看跌期权
    print(f"\n{'='*60}")
    print(f"【看跌期权 (Put)】")
    print(f"  执行价: ${atm_put['strike']:.2f}")
    print(f"  最新价: ${atm_put['lastPrice']:.2f}")
    print(f"  买价: ${atm_put['bid']:.2f}")
    print(f"  卖价: ${atm_put['ask']:.2f}")
    print(f"  隐含波动率: {atm_put['impliedVolatility']*100:.2f}%")
    
    # 使用 mibian 计算看跌期权希腊字母
    if atm_put['impliedVolatility'] > 0:
        put_greeks = mibian.BS(
            [current_price,
             atm_put['strike'],
             risk_free_rate * 100,
             days_to_expiry],
            volatility=atm_put['impliedVolatility'] * 100
        )
        
        print(f"\n  🔢 希腊字母:")
        print(f"     Delta:   {put_greeks.putDelta:.4f}  (价格变动1美元，期权价格变动)")
        print(f"     Gamma:   {put_greeks.gamma:.4f}  (Delta的变化率)")
        print(f"     Theta:   {put_greeks.putTheta:.4f}  (每天时间价值衰减)")
        print(f"     Vega:    {put_greeks.vega:.4f}  (波动率变动1%的影响)")
        print(f"     Rho:     {put_greeks.putRho:.4f}  (利率变动1%的影响)")
        
        print(f"\n  💡 理论价格: ${put_greeks.putPrice:.2f}")
        print(f"     市场价格: ${atm_put['lastPrice']:.2f}")
        print(f"     价差: ${abs(put_greeks.putPrice - atm_put['lastPrice']):.2f}")
        
        results.append({
            'Type': 'Put',
            'Strike': atm_put['strike'],
            'Market_Price': atm_put['lastPrice'],
            'Theoretical_Price': put_greeks.putPrice,
            'IV': atm_put['impliedVolatility'] * 100,
            'Delta': put_greeks.putDelta,
            'Gamma': put_greeks.gamma,
            'Theta': put_greeks.putTheta,
            'Vega': put_greeks.vega,
            'Rho': put_greeks.putRho
        })
    
    # 5. 生成汇总表
    if results:
        print(f"\n{'='*60}")
        print("📊 希腊字母汇总表")
        print(f"{'='*60}\n")
        df = pd.DataFrame(results)
        print(df.to_string(index=False))
        
        # 保存到CSV（统一保存到outputs目录）
        import os
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"options_greeks_{ticker_symbol}_{selected_expiry}.csv")
        df.to_csv(output_file, index=False)
        print(f"\n✅ 数据已保存到: {output_file}")
    
    return results


def compare_multiple_strikes(ticker_symbol, risk_free_rate=0.045, num_strikes=5):
    """
    比较多个执行价的希腊字母
    """
    print(f"\n{'='*60}")
    print(f"多执行价希腊字母对比分析 - {ticker_symbol}")
    print(f"{'='*60}\n")
    
    stock = yf.Ticker(ticker_symbol)
    
    # 获取当前价格
    try:
        current_price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice')
        if not current_price:
            hist = stock.history(period='1d')
            current_price = hist['Close'].iloc[-1]
        print(f"当前股价: ${current_price:.2f}\n")
    except:
        print("❌ 无法获取股价")
        return
    
    # 获取期权数据
    try:
        expiry_dates = stock.options
        selected_expiry = expiry_dates[0]
        days_to_expiry = calculate_days_to_expiry(selected_expiry)
        
        option_chain = stock.option_chain(selected_expiry)
        calls = option_chain.calls
        
        # 选择围绕当前价格的多个执行价
        calls = calls.sort_values('strike')
        calls['distance'] = abs(calls['strike'] - current_price)
        calls = calls.sort_values('distance').head(num_strikes)
        
        results = []
        
        for _, option in calls.iterrows():
            if option['impliedVolatility'] > 0:
                greeks = mibian.BS(
                    [current_price, option['strike'], risk_free_rate * 100, days_to_expiry],
                    volatility=option['impliedVolatility'] * 100
                )
                
                moneyness = (option['strike'] - current_price) / current_price * 100
                
                results.append({
                    'Strike': option['strike'],
                    'Moneyness_%': moneyness,
                    'Market_Price': option['lastPrice'],
                    'Theo_Price': greeks.callPrice,
                    'IV_%': option['impliedVolatility'] * 100,
                    'Delta': greeks.callDelta,
                    'Gamma': greeks.gamma,
                    'Theta': greeks.callTheta,
                    'Vega': greeks.vega
                })
        
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values('Strike')
            print(df.to_string(index=False, float_format='%.4f'))
            
            print(f"\n💡 解读:")
            print(f"   • Moneyness: 负值=价内(ITM), 0=平值(ATM), 正值=价外(OTM)")
            print(f"   • Delta: 接近1=深度价内, 接近0.5=平值, 接近0=深度价外")
            print(f"   • Gamma: 平值期权的Gamma最大")
            print(f"   • Theta: 平值期权的时间衰减最快")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")


if __name__ == "__main__":
    # 测试1: 单个股票的平值期权分析
    print("\n" + "="*60)
    print("测试 1: 苹果公司 (AAPL) 平值期权希腊字母")
    print("="*60)
    get_option_greeks("AAPL", risk_free_rate=0.045)
    
    # 测试2: 多执行价对比
    print("\n\n" + "="*60)
    print("测试 2: 多执行价希腊字母对比")
    print("="*60)
    compare_multiple_strikes("AAPL", risk_free_rate=0.045, num_strikes=7)
    
    # 测试3: 另一个股票
    print("\n\n" + "="*60)
    print("测试 3: 特斯拉 (TSLA) 期权分析")
    print("="*60)
    get_option_greeks("TSLA", risk_free_rate=0.045)
