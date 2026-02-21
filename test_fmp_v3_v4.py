
import requests
FMP_API_KEY = "yytaAKONtPbR5cBcx9azLeqlovaWDRQm"
url = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={FMP_API_KEY}"
print("V3 Profile AAPL:", requests.get(url).json())
url4 = f"https://financialmodelingprep.com/api/v4/company-outlook?symbol=AAPL&apikey={FMP_API_KEY}"
print("V4 Outlook AAPL:", requests.get(url4).json())
