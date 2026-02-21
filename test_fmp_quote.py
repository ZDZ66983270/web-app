
import requests
FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"
url = f"https://financialmodelingprep.com/api/v3/quote/0700.HK?apikey={FMP_API_KEY}"
print(requests.get(url).json())
