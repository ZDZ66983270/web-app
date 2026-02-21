import requests
from bs4 import BeautifulSoup
import json
import time

# 配置
STOCK_CODE = "00700" # 腾讯
URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"

def test_fetch():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Origin": "https://www1.hkexnews.hk",
        "Referer": URL
    })

    print(f"1. 访问页面以获取 ViewState: {URL}")
    try:
        resp = session.get(URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"请求失败: {e}")
        return

    soup = BeautifulSoup(resp.text, 'html.parser')

    # 提取 ViewState (ASP.NET/JSF页面的关键)
    viewstate_input = soup.find('input', {'name': 'javax.faces.ViewState'})
    if not viewstate_input:
        print("未找到 ViewState，可能是页面结构变更或反爬虫。")
        # 打印部分页面内容用于调试
        print(resp.text[:500])
        return
    
    viewstate = viewstate_input.get('value')
    print(f"成功获取 ViewState (长度: {len(viewstate)})")

    # 保存初始页面以供检查
    with open("hkex_initial.html", "w", encoding='utf-8') as f:
        f.write(resp.text)
    
    # 打印所有 Input 字段以辅助分析 Payload 结构
    print("\n[调试info] 页面检测到的部分 Input 字段:")
    inputs = soup.find_all(['input', 'select', 'textarea'])
    form_data = {}
    for i in inputs:
        name = i.get('name')
        if name:
            if 'ViewState' not in name:
                print(f"  - {i.name} | name={name} | id={i.get('id')} | value={i.get('value', 'N/A')[:20]}")
            # 保存默认值
            form_data[name] = i.get('value', '')
    
    # 2. 构造查询 Payload
    # 尝试基于 "searchForm" 的常见命名
    
    # 临时：等待查看 Input 输出后再决定 Key
    # 现在的 payload 可能是错的
    payload = form_data.copy()
    payload.update({
        'searchControl:txtStockCode': STOCK_CODE,
        'searchControl:txtFromDate': '20230101',
        'searchControl:txtToDate': '20250131',
        # 'searchControl:ddlTierOne': '1', # 1=Headlines category?
        # 'searchControl:ddlTierTwo': '-2',
        'searchControl:btnSearch': '搜索' # 模拟点击按钮
    })

    # 清理掉不需要的提交按钮 (如果存在多个 submit)
    # 通常保留 btnSearch 即可

    print(f"\n2. 尝试 POST 查询 (股票: {STOCK_CODE})...")
    try:
        post_resp = session.post(URL, data=payload, timeout=15)
        post_resp.raise_for_status()
        
        # 保存结果用于调试
        with open("hkex_response_debug.html", "w", encoding='utf-8') as f:
            f.write(post_resp.text)
            
        print("请求完成，正在检查结果...")
        # 简单的检查
        if "00700" in post_resp.text and "腾讯" in post_resp.text:
            print("✅ 页面响应中包含目标股票信息。")
        else:
            print("⚠️ 页面响应可能未包含目标数据。请检查 'hkex_response_debug.html'。")
            
        # 尝试提取链接
        res_soup = BeautifulSoup(post_resp.text, 'html.parser')
        # HKEX 结果通常在 class="doc-link" 或类似的结构中
        links = res_soup.find_all('a', href=True)
        pdf_links = [l['href'] for l in links if l['href'].endswith('.pdf')]
        
        print(f"发现 {len(pdf_links)} 个 PDF 链接:")
        for l in pdf_links[:5]:
            print(f"  - {l}")

    except Exception as e:
        print(f"POST 请求失败: {e}")

if __name__ == "__main__":
    test_fetch()
