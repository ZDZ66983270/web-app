
import requests
import json

def probe_cninfo_search(code):
    # Try different endpoint
    url = "http://www.cninfo.com.cn/new/information/topSearch/query"
    payload = {"keyWord": code, "maxNum": 10}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        r = requests.post(url, data=payload, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    res = probe_cninfo_search("600036")
    print(json.dumps(res, indent=2, ensure_ascii=False))
