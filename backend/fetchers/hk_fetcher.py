import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def fetch_hk_pdf(symbol: str, save_dir: str, mode: str = 'inc'):
    """
    Fetch HK annual reports PDFs from HKEX using Selenium.
    symbol: e.g. '00700' or 'HK:STOCK:00700'
    """
    # Clean symbol
    code = symbol.split(':')[-1]
    if '.' in code: code = code.split('.')[0]
    
    # Setup Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")
    
    driver = None
    try:
        print(f"   [HK] Launching Selenium for {code}...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        url = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"
        driver.get(url)
        time.sleep(3)
        
        # 1. Input Stock Code
        # Multiple selectors
        try:
            inp = driver.find_element(By.ID, "searchControl:txtStockCode")
            inp.clear()
            inp.send_keys(code)
        except:
             # Try alternate
             inp = driver.find_element(By.CSS_SELECTOR, "input.input-stockCode")
             inp.clear()
             inp.send_keys(code)
             
        # 2. Select Annual Report Category (Concept: Tier 1)
        # For simplicity, we search ALL documents first, then filter by title. 
        # Or we rely on keyword search.
        # Let's keep it simple: Search All + Title Filter.
        
        # 3. Click Search
        search_btn = None
        selectors = [
            (By.CLASS_NAME, "filter__btn-applyFilters-js"),
            (By.XPATH, "//a[contains(text(), '搜尋')]"),
            (By.CSS_SELECTOR, "a.btn-blue")
        ]
        for by, val in selectors:
            try:
                btns = driver.find_elements(by, val)
                for b in btns:
                    if b.is_displayed():
                        search_btn = b
                        break
                if search_btn: break
            except: continue
            
        if search_btn:
            driver.execute_script("arguments[0].click();", search_btn)
            # Wait for results
            time.sleep(5)
        else:
            print("   [HK] ❌ Search button not found.")
            return

        # 4. Parse Results
        # Results are in div.doc-link
        links = driver.find_elements(By.CSS_SELECTOR, "div.doc-link a")
        
        final_dir = os.path.join(save_dir, 'HK', code)
        os.makedirs(final_dir, exist_ok=True)
        
        count = 0
        for link in links:
            title = link.text.strip()
            href = link.get_attribute("href")
            
            # Filter: Annual Report or Annual Results
            # "年報", "年度報告", "Annual Report"
            if not any(k in title for k in ["年報", "年度報告", "Annual Report", "業績公告"]): 
                continue
            if "摘要" in title or "通知" in title: 
                continue
                
            # Date is usually in a sibling div or not easily accessible in simple view
            # We construct name from Title
            # De-duplicate by title?
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ','-','_')]).strip()
            filename = f"{safe_title[:50]}.pdf"
            filepath = os.path.join(final_dir, filename)
            
            count += 1
            if os.path.exists(filepath): continue
            
            print(f"      ⬇️ Downloading {filename}...")
            try:
                r_file = requests.get(href, timeout=30)
                with open(filepath, "wb") as f:
                    f.write(r_file.content)
            except: pass
            
        print(f"   [HK] Downloaded {count} files to {final_dir}")
        return count > 0
        
    except Exception as e:
        print(f"   ❌ HK Fetch Error: {e}")
        return False
    finally:
        if driver: driver.quit()
