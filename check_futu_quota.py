from futu import *

def check_quota():
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data = quote_ctx.get_history_kl_quota()
        if ret == RET_OK:
            print("📊 Futu Historical K-Line Quota:")
            print(data)
        else:
            print(f"❌ Failed to get quota: {data}")
        quote_ctx.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_quota()
