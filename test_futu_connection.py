
from futu import *
import sys

print("📡 正在尝试连接 Futu OpenD (127.0.0.1:11111)...")

try:
    # 尝试连接行情上下文
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    print("✅ 连接成功！")
    
    # 获取市场快照测试
    # 测试一只港股 00700
    ret, data = quote_ctx.get_market_snapshot(['HK.00700'])
    if ret == RET_OK:
        print(f"📊 腾讯控股 (00700) 当前价格: {data['last_price'][0]}")
    else:
        print(f"❌ 获取快照失败: {data}")
        
    # 获取期权链测试
    # 尝试获取 00700 的期权链
    print("🔍 正在查询腾讯控股期权链...")
    ret, expiry_list = quote_ctx.get_option_expiration_date(code='HK.00700')
    if ret == RET_OK:
        print(f"✅ 获取到期日列表成功: {expiry_list.iloc[0]['strike_time']} 等 {len(expiry_list)} 个")
    else:
        print(f"❌ 获取期权到期日失败: {expiry_list}")

    quote_ctx.close()
    print("👋 连接已关闭")
    sys.exit(0)

except Exception as e:
    print(f"❌ 连接异常: {e}")
    print("💡 请检查 Futu OpenD 是否已启动，并监听在 11111 端口。")
    sys.exit(1)
