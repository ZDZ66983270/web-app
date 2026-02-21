
import requests
FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"
code = "0700.HK"
url = f"https://financialmodelingprep.com/stable/ratios?symbol={code}&period=quarter&limit=20&apikey={FMP_API_KEY}"
r = requests.get(url)
print(r.json())
