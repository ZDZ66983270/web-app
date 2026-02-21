from sec_edgar_downloader import Downloader
import os

# 创建下载器
# 注意：SEC 要求提供公司名称和联系电子邮件
dl = Downloader("VERA-AI-Bot", "admin@vera-analytics.local")

print("开始下载 AAPL 的最后一份 10-K 报告...")
# 仅下载最后一份以节省时间
dl.get("10-K", "AAPL", limit=1)

print("下载完成。正在检查目录结构...")
# 默认下载到当前目录下的 'sec-edgar-filings' 文件夹
if os.path.exists("sec-edgar-filings"):
    print("成功找到 'sec-edgar-filings' 目录。")
    # 列出下载的内容
    for root, dirs, files in os.walk("sec-edgar-filings"):
        for file in files:
            print(f"找到文件: {os.path.join(root, file)}")
else:
    print("未找到下载目录。")
