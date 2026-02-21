
import requests
FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"
url = f"https://financialmodelingprep.com/api/v3/search?query=Tencent&limit=10&apikey={FMP_API_KEY}"
print(requests.get(url).json())
