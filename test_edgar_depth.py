from sec_edgar_downloader import Downloader
import os
from datetime import date

# 使用与之前相同的凭据
dl = Downloader("VERA-AI-Bot", "admin@vera-analytics.local")

print("尝试获取 AAPL 的所有 10-K 记录（从 1990 年开始）...")
# 设置之后的时间以探索深度
dl.get("10-K", "AAPL", after="1990-01-01")

# 检查下载的目录
path = "sec-edgar-filings/AAPL/10-K"
if os.path.exists(path):
    filings = sorted(os.listdir(path))
    print(f"共发现 {len(filings)} 份 10-K 报告。")
    if filings:
        print(f"最早的一份是: {filings[0]}")
        print(f"最晚的一份是: {filings[-1]}")
else:
    print("未发现下载内容。")
