from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

def fetch_hkex_with_selenium(stock_code="00700"):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") # Ensure desktop layout
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")

    print("1. 启动 Chrome 浏览器...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        url = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"
        print(f"2. 访问页面: {url}")
        driver.get(url)

        # Handle potential "cookie" or "disclaimer" popups if any (not common on this specific page)

        print("3. 等待输入框加载...")
        # HKEX input ID is often 'searchStockCode' or similar. 
        # Inspecting standard element from knowlege: usually 'searchControl:txtStockCode'
        # Or look for input with placeholder '股份代号'
        
        # Wait for the main input
        wait = WebDriverWait(driver, 15)
        
        # Try finding by likely IDs or CSS selectors
        input_element = None
        possible_selectors = [
            (By.NAME, "searchControl:txtStockCode"),
            (By.ID, "searchControl:txtStockCode"), 
            (By.XPATH, "//input[contains(@placeholder, '股份代号')]"),
            (By.XPATH, "//input[contains(@placeholder, 'Stock Code')]"),
            (By.ID, "searchStockCode")
        ]
        
        for by, val in possible_selectors:
            try:
                print(f"  - 尝试定位元素: {val}")
                input_element = driver.find_element(by, val)
                if input_element:
                    print(f"  ✅ 成功定位输入框: {val}")
                    break
            except:
                continue
        
        if not input_element:
            print("❌ 无法找到股票代码输入框。即将把页面HTML保存为 debug_selenium_page.html")
            with open("debug_selenium_page.html", "w", encoding='utf-8') as f:
                f.write(driver.page_source)
            return

        # DUMP PAGE SOURCE NOW that input is loaded
        print("🔍 已加载搜索面板，由于之前找不到按钮，现在保存完整渲染 HTML 以供调试...")
        with open("hkex_rendered.html", "w", encoding='utf-8') as f:
            f.write(driver.page_source)

        print(f"4. 输入代码: {stock_code}")
        input_element.clear()
        input_element.send_keys(stock_code)
        
        # Find search button by multiple strategies including text
        search_btn = None
        btn_selectors = [
            (By.CLASS_NAME, "filter__btn-applyFilters-js"),
            (By.XPATH, "//a[contains(@class, 'filter__btn-applyFilters-js')]"),
            (By.XPATH, "//a[contains(text(), '搜尋')]"),
            (By.CSS_SELECTOR, "a.btn-blue")
        ]
        
        for by, val in btn_selectors:
            try:
                elements = driver.find_elements(by, val)
                for btn in elements:
                    if btn.is_displayed():
                        print(f"  ✅ 成功定位可见的搜索按钮: {val}")
                        search_btn = btn
                        break
                if search_btn: break
            except:
                continue
        
        if search_btn:
            print("5. 点击搜索...")
            # Scroll to view
            driver.execute_script("arguments[0].scrollIntoView(true);", search_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", search_btn)
        else:
            print("❌ 未找到搜索按钮，尝试直接回车...")
            input_element.send_keys("\n")

        print("6. 等待结果加载 (20秒)...")
        time.sleep(5) 
        
        # Check for specific result containers
        # Common HKEX result row class: 'doc-link' inside 'component-list-content'
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "component-list-content")))
            print("  ✅ 检测到结果列表容器。")
        except:
            print("  ⚠️ 未检测到结果列表容器，可能搜索未完成或无结果。")

        # Extract results
        links = driver.find_elements(By.TAG_NAME, "a")
        pdf_links = []
        for l in links:
            href = l.get_attribute("href")
            text = l.text.strip()
            if href and ".pdf" in href:
                # Filter for non-generic links
                if "hkexnews.hk" in href and "search" not in href.lower():
                     # Try to match typical report names
                     pdf_links.append((text, href))
        
        print(f"\n✅ 发现 {len(pdf_links)} 个 PDF 文档 (展示前 10 个):")
        unique_links = []
        seen = set()
        for p in pdf_links:
            if p[1] not in seen:
                unique_links.append(p)
                seen.add(p[1])

        for i, (txt, link) in enumerate(unique_links[:10]):
            print(f"  [{i+1}] {txt[:30]}... -> {link}")
            
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    fetch_hkex_with_selenium()
