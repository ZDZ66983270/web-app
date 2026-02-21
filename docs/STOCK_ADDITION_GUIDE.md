# 新增个股数据下载顺序标准 (SOP)

为了确保财务指标（如 EPS、PE）计算正确，新增个股时必须遵循以下顺序。

## 📥 下载顺序

### 第一步：更新 Watchlist
将新标的加入数据库的 `watchlist` 或 `index` 表。

### 第二步：下载财报数据 (Financials) ⭐️ **关键**
**运行脚本**：`python3 fetch_financials.py`
- **原因**：必须先获得公司的**记账货币**（如美元、人民币）和**历史净利润 (Net Income TTM)**。
- **结果**：数据存入 `financial_fundamentals` 表。

### 第三步：下载行情历史 (Market History)
**运行脚本**：`python3 download_raw_data.py` (或 `daily_incremental_update.py`)
- **原因**：获取股价数据。
- **结果**：数据存入 `raw_market_data` 随后通过 ETL 转入 `market_data_daily`。

### 第四步：计算/补全指标 (Metrics)
**运行脚本**：`python3 backfill_historical_eps.py` (针对历史) 或 `daily_incremental_update.py` (针对最新)
- **原因**：此时程序会从 yfinance 获取**总股数**，结合第二步的**净利润**和**货币单位**，计算出单位统一的 EPS，并存入日线表。

---

## ⚠️ 常见问题

### 为什么不能先下载行情？
如果先下载行情，ETL 过程会因为找不到对应的财报数据而无法计算 EPS，导致 PE (市盈率) 等指标显示为 NULL 或 0。

### 为什么港股 PE 会出错？
如果你跳过了第二步（财报下载），程序可能无法正确识别汇丰（USD）或腾讯（CNY）的财务单位，从而导致计算出的 PE 偏差 7.8 倍。
