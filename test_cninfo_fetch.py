import requests
import json
import time

# 配置
STOCK_CODE = "000002,gssz0000002" # 万科A (Code, OrgId)
URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
BASE_PDF_URL = "http://static.cninfo.com.cn/"

def test_cninfo_fetch():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search&lastPage=index"
    }

    # 构造查询参数 (针对 A 股年报)
    payload = {
        "stock": STOCK_CODE,
        "tabName": "fulltext",
        "pageSize": 30,
        "pageNum": 1,
        "column": "szse", # 深交所
        "category": "category_ndbg_szsh;", # 年报类别
        "plate": "sz",
        "seDate": "", # 不限制时间
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true"
    }

    print(f"1. 请求 CNINFO 接口: {URL}")
    print(f"   参数: stock={STOCK_CODE}, category=category_ndbg_szsh")
    
    try:
        resp = requests.post(URL, data=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        
        # 提取公告列表
        announcements = data.get("announcements", [])
        if not announcements:
            print("⚠️ 未找到任何公告，请检查 OrgId 或参数。")
            print(f"API 响应预览: {str(data)[:200]}")
            return

        print(f"\n✅ 成功发现 {len(announcements)} 条公告 (展示前 10 条):")
        
        pdf_count = 0
        for ann in announcements:
            title = ann.get("announcementTitle", "No Title").strip()
            adjunct_url = ann.get("adjunctUrl")
            sec_name = ann.get("secName")
            
            # 过滤掉非年报摘要 (如果不想要摘要，可以根据标题过滤，这里简单展示所有)
            # 拼接 PDF 链接
            if adjunct_url:
                pdf_link = BASE_PDF_URL + adjunct_url
                print(f"  [{pdf_count+1}] {sec_name} - {title}")
                print(f"      -> {pdf_link}")
                pdf_count += 1
                if pdf_count >= 10:
                    break
        
    except Exception as e:
        print(f"请求发生异常: {e}")

if __name__ == "__main__":
    test_cninfo_fetch()
