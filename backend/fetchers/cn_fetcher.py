import os
import requests
import logging
import datetime

def fetch_cn_pdf(symbol: str, save_dir: str, mode: str = 'inc'):
    """
    Unified Fetcher for CN (A-Share) and HK (Hong Kong) reports from CNINFO.
    symbol: e.g. 'CN:STOCK:600309' or 'HK:STOCK:00700'
    """
    # 1. Resolve Metadata
    code = symbol.split(':')[-1]
    meta = get_cninfo_orgid(code)
    
    if not meta or not meta.get('orgId'):
        print(f"   [CNINFO] ❌ Metadata resolution failed for {symbol}. Skipping PDF fetch.")
        return False

    org_id = meta['orgId']
    category = meta.get('category', 'A股')
    stock_type = meta.get('type', 'shj')
    
    # 2. Determine Directory and Fetch Parameters
    # Default (A-Share)
    market_folder = 'CN'
    column = "szse" if stock_type == "shj" else "sse"
    plate = "sz" if "sz" in stock_type else "sh"
    
    # HK Specific Overrides
    if category == '港股' or stock_type == 'hke':
        market_folder = 'HK'
        column = "hke"
        plate = "hk"
        print(f"   [CNINFO] Routing to HKEX mirror on CNINFO for {symbol}...")

    final_dir = os.path.join(save_dir, market_folder, code)
    os.makedirs(final_dir, exist_ok=True)
    
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    stock_param = f"{code},{org_id}"

    sec_name_resolved = None
    count = 0
    # 1. Fetch multiple pages without restrictive categories for maximum robustness
    if mode == 'inc':
        # Incremental mode: Look back 2 years
        cutoff_date = datetime.date.today().replace(year=datetime.date.today().year - 2).strftime("%Y-%m-%d")
    else:
        # Full mode: Look back 10 years
        cutoff_date = datetime.date.today().replace(year=datetime.date.today().year - 10).strftime("%Y-%m-%d")
    
    earliest_seen = None
    for page in range(1, 101): 
        payload = {
            "stock": stock_param,
            "tabName": "fulltext",
            "pageSize": 30, 
            "pageNum": str(page),
            "column": column,
            "plate": plate,
            "isHLtitle": "true"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            resp = requests.post(url, data=payload, headers=headers, timeout=10)
            data = resp.json()
            
            announcements = data.get("announcements", [])
            if not announcements:
                break

            for ann in announcements:
                # Announcement Time filtering
                ts = ann.get("announcementTime", 0) / 1000
                dt_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                
                if earliest_seen is None or dt_str < earliest_seen:
                     earliest_seen = dt_str
                if dt_str < cutoff_date:
                     continue # Skip reports older than 10 years

                title = ann.get("announcementTitle", "").strip()
                sec_name = ann.get("secName", "").strip()
                if not sec_name_resolved and sec_name: sec_name_resolved = sec_name
                
                # CRITICAL: ONLY keep reports that are full disclosures
                is_valid_report = False
                # Annual/Interim/Quarterly
                if any(x in title for x in ["年度报告", "半年度报告", "季度报告", "中期报告"]):
                     is_valid_report = True
                elif "业绩" in title and any(x in title for x in ["一季度", "三季度", "公告", "首三季"]):
                     # For HK, quarterly updates are often "业绩公告"
                     is_valid_report = True

                # HK: CNINFO titles are often non-standard ("中期业绩", "盈利公布", etc.)
                if not is_valid_report and (category == '港股' or stock_type == 'hke'):
                    hk_title_allow = [
                        "中期业绩", "业绩公布", "盈利公布", "全年业绩", "末期业绩", "初步业绩", "业绩公告",
                        "Interim Results", "Annual Results", "Final Results", "Profit Announcement", "Earnings Announcement"
                    ]
                    if any(x in title for x in hk_title_allow):
                        is_valid_report = True
                
                # REJECT noise early
                # Note: For HK we relaxed '公告' above, but still reject other noise
                reject_keywords = ["摘要", "取消", "提示性", "说明", "履职", "工作报告", "报告书", "更正", "解释", "情况报告", "工作制度", "督导报告", "核查报告", "建议", "补充", "更新"]
                if any(x in title for x in reject_keywords):
                    # EXCEPTION: If it's a valid report type, but title contains '摘要', we prefer full report
                    is_valid_report = False
                    
                if not is_valid_report:
                    continue
                
                adj_url = ann.get("adjunctUrl")
                if not adj_url: continue
                pdf_url = "http://static.cninfo.com.cn/" + adj_url
                
                display_title = title
                if sec_name and sec_name not in title:
                     display_title = f"{sec_name}_{title}"
                
                safe_title = "".join([c for c in display_title if c.isalnum() or c in (' ','-','_')]).strip()
                safe_title = safe_title.replace(' ', '_')
                
                filename = f"{dt_str}_{safe_title}.pdf"
                filepath = os.path.join(final_dir, filename)
                
                if os.path.exists(filepath):
                    continue
                    
                # Download
                print(f"      ⬇️ Downloading {filename}...")
                count += 1
                try:
                    r_pdf = requests.get(pdf_url, timeout=30)
                    with open(filepath, "wb") as f:
                        f.write(r_pdf.content)
                except Exception as e:
                    print(f"      ❌ Download failed: {e}")
                    
            if len(announcements) < 30: 
                break
                    
        except Exception as e:
            print(f"   ❌ CN Fetch Error (Page {page}): {e}")
            break

    # 2. Cleanup legacy/duplicate or OLD filenames
    # We now also cleanup anything < cutoff_date if requested
    if sec_name_resolved:
        all_files = os.listdir(final_dir)
        for f in all_files:
            if not f.endswith(".pdf"): continue
            parts = f.split('_')
            if len(parts) >= 1 and parts[0].count('-') == 2:
                dt_prefix = parts[0]
                
                # Cleanup too old files
                if dt_prefix < cutoff_date:
                    print(f"      🚮 Cleaning up old report (>10y): {f}")
                    try: os.remove(os.path.join(final_dir, f))
                    except: pass
                    continue

                if sec_name_resolved not in f:
                    # Check if standard version exists
                    if any(dt_prefix in f2 and sec_name_resolved in f2 for f2 in all_files if f != f2):
                        print(f"      🚮 Cleaning up legacy/duplicate: {f}")
                        try: os.remove(os.path.join(final_dir, f))
                        except: pass

    if earliest_seen:
        print(f"   [CNINFO] Earliest announcement seen: {earliest_seen}")
    print(f"   [CN] Downloaded {count} new files to {final_dir}")
    return count > 0 or len(os.listdir(final_dir)) > 0

def get_cninfo_orgid(code: str):
    """
    Query CNINFO for the mapping of stock code to internal orgId and metadata.
    Returns: dict with 'orgId', 'category', 'type' or None
    """
    url = "http://www.cninfo.com.cn/new/information/topSearch/query"
    try:
        payload = {"keyWord": code, "maxNum": 10}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.post(url, data=payload, headers=headers, timeout=5)
        data = r.json()
        for item in data:
            # For HK stocks, code is often '00700', item code is also '00700'
            # We need to be careful with A-share vs HK-share overlap
            if item.get("code") == code:
                meta = {
                    "orgId": item.get("orgId"),
                    "category": item.get("category"), # e.g., 'A股', '港股'
                    "type": item.get("type"),         # e.g., 'shj' (A), 'hke' (HK)
                    "zwjc": item.get("zwjc")
                }
                print(f"   [CNINFO] Resolved metadata for {code}: {meta['orgId']} ({meta['category']})")
                return meta
    except Exception as e:
        print(f"   [CNINFO] ❌ Error resolving OrgID: {e}")
    return None
