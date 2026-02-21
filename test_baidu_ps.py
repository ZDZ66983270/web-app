
import requests
import pandas as pd

def test_baidu_ps(code):
    url = "https://gushitong.baidu.com/opendata"
    params = {
        "openapi": "1",
        "dspName": "iphone",
        "tn": "tangram",
        "client": "app",
        "query": "市销率",
        "code": code,
        "resource_id": "51171",
        "srcid": "51171",
        "market": "hk",
        "tag": "市销率",
        "skip_industry": "1",
        "chart_select": "全部",
        "finClientType": "pc"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"🌐 Testing Baidu PS for {code}...")
    response = requests.get(url, params=params, headers=headers, timeout=10)
    data = response.json()
    
    try:
        results = data.get("Result", [])
        if not results:
            print("❌ No results")
            return
        
        display_data = results[0].get("DisplayData", {}).get("resultData", {}).get("tplData", {}).get("result", {})
        chart_info = display_data.get("chartInfo", [])
        
        if not chart_info:
            print("❌ No chartInfo")
            return
            
        body = chart_info[0].get("body", [])
        if not body:
            print("❌ No body data")
            return
        
        df = pd.DataFrame(body, columns=['date', 'value'])
        print(f"✅ Success! Found {len(df)} records.")
        print(df.tail(5))
    except Exception as e:
        print(f"❌ Error parsing: {e}")

if __name__ == "__main__":
    test_baidu_ps("00700")
