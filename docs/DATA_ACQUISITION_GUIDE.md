# 数据获取途径完整梳理

## 📅 更新日期
2026-01-15

> **重要说明**: 本文档已更新以反映系统的**实际实现**情况。

---

## 📊 一、日线行情数据 (OHLCV)

### A股

| 数据源 | 接口 | 字段 | 历史范围 | 推荐度 | 备注 |
|--------|------|------|---------|--------|------|
| **yfinance** | `ticker.history()` | Open,High,Low,Close,Volume,Dividends,Stock Splits | 上市至今 | ⭐⭐⭐⭐ | **当前使用** |
| AkShare | `stock_zh_a_hist()` | 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率 | 上市至今 | ⭐⭐⭐⭐ | 备选（数据更全） |

**示例代码（当前实现）**:
```python
import yfinance as yf
ticker = yf.Ticker("600519.SS")
df = ticker.history(period="max", auto_adjust=True)
```

### 港股

| 数据源 | 接口 | 字段 | 历史范围 | 推荐度 | 备注 |
|--------|------|------|---------|--------|------|
| **yfinance** | `ticker.history()` | Open,High,Low,Close,Volume,Dividends,Stock Splits | 上市至今 | ⭐⭐⭐⭐ | **当前使用** |
| AkShare | `stock_hk_hist()` | 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率 | 上市至今 | ⭐⭐⭐⭐ | 备选（数据更全） |
| Futu API | `request_history_kline()` | code,time_key,open,close,high,low,volume,turnover,change_rate,last_close,**pe_ratio**,turnover_rate | 完整历史 | ⭐⭐⭐ | 备用,含PE,需FutuOpenD |

**示例代码（当前实现）**:
```python
import yfinance as yf
ticker = yf.Ticker("0700.HK")
df = ticker.history(period="max", auto_adjust=True)
```

### 美股

| 数据源 | 接口 | 字段 | 历史范围 | 推荐度 | 备注 |
|--------|------|------|---------|--------|------|
| **yfinance** | `ticker.history()` | Open,High,Low,Close,Volume,Dividends,Stock Splits | 上市至今 | ⭐⭐⭐⭐ | **当前使用** |
| AkShare | `stock_us_hist()` | 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率 | 上市至今 | ⭐⭐⭐⭐ | 备选 |

**示例代码（当前实现）**:
```python
import yfinance as yf
ticker = yf.Ticker("AAPL")
df = ticker.history(period="max", auto_adjust=True)
```

---

## 💹 二、市盈率 (PE) 数据

### A股 - 个股历史每日PE ⭐⭐⭐⭐

| 数据源 | 接口 | PE字段 | 数据量 | 推荐度 |
|--------|------|--------|--------|--------|
| **AkShare** | `stock_value_em()` | PE(TTM), PE(静), PEG值 | 上市至今每日 | ⭐⭐⭐⭐ |

**示例代码**:
```python
import akshare as ak
df = ak.stock_value_em(symbol="600519")
# 返回字段: 数据日期, 当日收盘价, PE(TTM), PE(静), PEG值, 市净率, 市销率, 市现率
# 贵州茅台: 1,946条历史数据, 100%完整
```

**数据示例**:
```
数据日期      PE(TTM)  PE(静)   PEG值
2026-01-08   19.64    20.51    1.22
```

### 港股 - 个股历史每日PE (重要更新) ⭐⭐⭐⭐⭐

| 数据源 | 接口 | PE类型 | 历史范围 | 推荐度 | 备注 |
|--------|------|--------|---------|--------|------|
| Futu API | `request_history_kline()` | **Static PE** | 完整历史 | ⭐⭐⭐⭐⭐ | **首选: 历史回填 (含分页)** |
| Futu API | `get_market_snapshot()` | **TTM PE** | 仅最新 | ⭐⭐⭐⭐⭐ | **首选: 实时动态 PE** |
| ~~Baidu~~ | ~~`fetch_hk_valuation_baidu_direct()`~~ | ~~TTM PE~~ | 完整历史 | ⭐⭐⭐ | **备用 (已降级)** |

**示例代码 (Futu - 推荐)**:
```python
import futu as ft
quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)

# 1. 历史静态 PE (Static)
ret, df, _ = quote_ctx.request_history_kline(code='HK.00700', ...)
# 包含 pe_ratio 字段 (Static)

# 2. 实时动态 PE (TTM)
ret, snapshot = quote_ctx.get_market_snapshot(['HK.00700'])
pe_ttm = snapshot['pe_ttm_ratio'][0]
```

### 美股 - 个股PE ⭐⭐

| 数据源 | 接口 | PE字段 | 数据类型 | 推荐度 |
|--------|------|--------|---------|--------|
| yfinance | `ticker.info` | trailingPE, forwardPE | **仅实时快照** | ⭐⭐ |
| AkShare | `stock_us_famous_spot_em()` | 市盈率 | **仅实时快照** | ⭐⭐ |

**❌ 美股无历史每日PE数据**

**解决方案**:
1. 自行计算: `PE = Price / EPS`
2. 定期记录实时PE值到数据库
3. 使用付费数据源

### 市场/板块整体PE

| 数据源 | 接口 | 适用范围 | 推荐度 |
|--------|------|---------|--------|
| AkShare | `stock_a_ttm_lyr()` | A股市场整体 | ⭐⭐⭐ |
| AkShare | `stock_market_pe_lg()` | 上证/深证/创业板/科创板 | ⭐⭐⭐ |

---

## 📈 三、市净率 (PB) 数据

### A股 - 个股历史每日PB ⭐⭐⭐⭐

| 数据源 | 接口 | PB字段 | 数据量 |
|--------|------|--------|--------|
| **AkShare** | `stock_value_em()` | 市净率 | 上市至今每日 |

**示例代码**:
```python
import akshare as ak
df = ak.stock_value_em(symbol="600519")
# 同时包含: PE(TTM), PE(静), 市净率, 市销率, 市现率, PEG值
```

### 港股 - 个股历史每日PB ⭐⭐⭐⭐⭐

| 数据源 | 接口 | 历史范围 | 推荐度 | 备注 |
|--------|------|---------|--------|------|
| **Baidu** | `fetch_hk_valuation_baidu_direct()` | 完整历史 | ⭐⭐⭐⭐⭐ | **推荐: 响应快,数据新** |
| ~~AkShare~~ | ~~`stock_hk_indicator_eniu()`~~ | **止于2022** | ❌ | **已停更** |
| ~~AkShare~~ | ~~`stock_hk_valuation_baidu()`~~ | - | ❌ | **目前接口报错** |

**示例代码 (推荐)**:
```python
# 内部已封装调用百度直连接口
df = fetch_hk_valuation_baidu_direct(code="00700", indicator="市净率")
```

### 美股 - 个股PB ⭐⭐

| 数据源 | 接口 | PB字段 | 数据类型 |
|--------|------|--------|---------|
| yfinance | `ticker.info` | priceToBook | **仅实时快照** |

**❌ 美股无历史每日PB数据**

---

## 📑 四、财报数据

### A股财报 ⭐⭐⭐⭐

| 数据源 | 接口 | 数据类型 | 推荐度 |
|--------|------|---------|--------|
| **AkShare** | `stock_financial_report_sina()` | 资产负债表,利润表,现金流量表 | ⭐⭐⭐⭐ |
| **AkShare** | `stock_yjbb_em()` | 业绩报表 | ⭐⭐⭐⭐ |
| **AkShare** | `stock_yjyg_em()` | 业绩预告 | ⭐⭐⭐ |
| yfinance | `ticker.financials` | 财务报表 | ⭐⭐⭐ |

**示例代码**:
```python
import akshare as ak

# 业绩报表
df = ak.stock_yjbb_em(date="20231231")

# 资产负债表
df = ak.stock_financial_report_sina(stock="600519", symbol="资产负债表")

# 利润表
df = ak.stock_financial_report_sina(stock="600519", symbol="利润表")

# 现金流量表
df = ak.stock_financial_report_sina(stock="600519", symbol="现金流量表")
```

### 港股财报 ⭐⭐⭐

| 数据源 | 接口 | 数据类型 | 推荐度 |
|--------|------|---------|--------|
| **AkShare** | `stock_hk_profit_sheet_em()` | 利润表 | ⭐⭐⭐ |
| **AkShare** | `stock_hk_balance_sheet_em()` | 资产负债表 | ⭐⭐⭐ |
| **AkShare** | `stock_hk_cash_flow_sheet_em()` | 现金流量表 | ⭐⭐⭐ |
| yfinance | `ticker.financials` | 财务报表 | ⭐⭐⭐ |

### 美股财报 ⭐⭐⭐

| 数据源 | 接口 | 数据类型 | 推荐度 |
|--------|------|---------|--------|
| **yfinance** | `ticker.financials` | 利润表 | ⭐⭐⭐⭐ |
| **yfinance** | `ticker.balance_sheet` | 资产负债表 | ⭐⭐⭐⭐ |
| **yfinance** | `ticker.cashflow` | 现金流量表 | ⭐⭐⭐⭐ |
| AkShare | `stock_us_fundamental_em()` | 财务报表 | ⭐⭐⭐ |

**示例代码**:
```python
import yfinance as yf

ticker = yf.Ticker("AAPL")

# 年度财报
annual_financials = ticker.financials
annual_balance = ticker.balance_sheet
annual_cashflow = ticker.cashflow

# 季度财报
quarterly_financials = ticker.quarterly_financials
quarterly_balance = ticker.quarterly_balance_sheet
quarterly_cashflow = ticker.quarterly_cashflow
```

---

## 📊 五、其他估值指标

### 市销率 (PS)

| 市场 | 数据源 | 接口 | 字段 |
|------|--------|------|------|
| A股 | AkShare | `stock_value_em()` | 市销率 |
| 港股 | ❌ | - | - |
| 美股 | yfinance | `ticker.info` | priceToSalesTrailing12Months |

### 市现率 (PCF)

| 市场 | 数据源 | 接口 | 字段 |
|------|--------|------|------|
| A股 | AkShare | `stock_value_em()` | 市现率 |
| 港股 | AkShare | `stock_hk_valuation_baidu()` | value (indicator="市现率") |
| 美股 | ❌ | - | - |

### 股息率

| 市场 | 数据源 | 接口 | 字段 |
|------|--------|------|------|
| A股 | AkShare | `stock_dividend_cninfo()` | 股息率 |
| 港股 | AkShare | `stock_hk_indicator_eniu()` | dv (indicator="股息率") |
| 美股 | yfinance | `ticker.info` | dividendYield |

### ROE

| 市场 | 数据源 | 接口 | 字段 |
|------|--------|------|------|
| A股 | AkShare | 财报计算 | - |
| 港股 | AkShare | `stock_hk_indicator_eniu()` | roe (indicator="ROE") |
| 美股 | yfinance | `ticker.info` | returnOnEquity |

---

## 🎯 六、推荐方案总结

### 最佳实践

#### A股数据获取
```python
import akshare as ak

# 1. 日线行情
df_kline = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="qfq")

# 2. 估值指标 (PE, PB, PS, 市现率, PEG)
df_valuation = ak.stock_value_em(symbol="600519")

# 3. 财报数据
df_profit = ak.stock_financial_report_sina(stock="600519", symbol="利润表")
df_balance = ak.stock_financial_report_sina(stock="600519", symbol="资产负债表")
df_cashflow = ak.stock_financial_report_sina(stock="600519", symbol="现金流量表")
```

#### 港股数据获取
```python
import akshare as ak

# 1. 日线行情 (AkShare - 推荐)
df_kline = ak.stock_hk_hist(symbol="00700", period="daily", adjust="qfq")

# 2. 估值指标 (Futu API - 推荐)
# 静态 PE 通过历史 K 线获取
# TTM PE 通过市场快照获取 (仅最新)
fetch_hk_valuation_futu(symbol="HK:STOCK:00700", ...)

# 3. 财报数据
df_profit = ak.stock_hk_profit_sheet_em(symbol="00700")

# 备用方案: Futu API (需要 FutuOpenD)
# import futu as ft
# quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
# ret, df_kline, _ = quote_ctx.request_history_kline(
#     code='HK.00700',
#     ktype=ft.KLType.K_DAY,
#     autype=ft.AuType.QFQ
# )
# 包含: open, close, high, low, volume, pe_ratio
```

#### 美股数据获取
```python
import yfinance as yf
import akshare as ak

ticker = yf.Ticker("AAPL")

# 1. 日线行情
df_kline = ticker.history(period="max")

# 2. 实时估值指标
pe = ticker.info['trailingPE']
pb = ticker.info['priceToBook']
ps = ticker.info['priceToSalesTrailing12Months']

# 3. 财报数据
df_financials = ticker.financials
df_balance = ticker.balance_sheet
df_cashflow = ticker.cashflow

# 4. 或使用 AkShare
df_kline_ak = ak.stock_us_hist(symbol="105.AAPL", period="daily")
```

---

## ⚠️ 七、重要注意事项

### 1. 数据源选择原则（实际实现）

- **A股**: 当前使用 yfinance, 备选 AkShare (数据更全)
- **港股**: 当前使用 yfinance, 备选 AkShare (数据更全)
- **美股**: 当前使用 yfinance

### 2. PE数据获取策略

| 市场 | 历史每日PE | 实时PE | 推荐方案 |
|------|-----------|--------|---------|
| A股 | ✅ AkShare | ✅ AkShare | 直接使用 `stock_value_em()` |
| 港股 | ✅ Futu (Static) | ✅ Futu (Snapshot) | 使用 `request_history_kline` + `get_market_snapshot` |
| 美股 | ❌ 无 | ✅ yfinance | 自行计算或定期记录 |

### 3. 数据质量对比

| 数据源 | 数据完整性 | 更新频率 | 稳定性 | 免费 |
|--------|-----------|---------|--------|------|
| **AkShare** | ⭐⭐⭐⭐ | 每日 | ⭐⭐⭐⭐ | ✅ |
| **Futu API** | ⭐⭐⭐⭐ | 实时 | ⭐⭐⭐⭐ | ✅ (需FutuOpenD) |
| **yfinance** | ⭐⭐⭐ | 每日 | ⭐⭐⭐ | ✅ |

### 4. 限制与注意

- **Futu API**: 需要下载并运行 FutuOpenD 程序
- **AkShare**: 部分接口有访问频率限制
- **yfinance**: 美股历史PE需自行计算
- **数据延迟**: 所有免费数据源都有一定延迟

### 5. 日线数据保存判断规则

**目的**: 只保存已收盘的数据，排除盘中数据

#### 市场收盘时间

| 市场 | 时区 | 收盘时间 | 时间戳格式 |
|------|------|---------|-----------|
| **A股 (CN)** | Asia/Shanghai | 15:00 | `YYYY-MM-DD 15:00:00` |
| **港股 (HK)** | Asia/Hong_Kong | 16:00 | `YYYY-MM-DD 16:00:00` |
| **美股 (US)** | America/New_York | 16:00 EST | `YYYY-MM-DD 16:00:00` |

#### 判断逻辑

```python
# 1. 转换为市场当地时间
now_local = datetime.now(market_timezone)
today = now_local.date()
current_time = now_local.time()

# 2. 判断数据日期
data_date = yfinance_timestamp.date()

if data_date < today:
    save()  # 历史数据 → 保存
elif data_date == today:
    if current_time >= market_close_time:
        save()  # 今日已收盘 → 保存
    else:
        skip()  # 今日未收盘 → 跳过
else:
    skip()  # 未来数据 → 跳过
```

#### 实际案例（北京时间 2026-01-09 12:53）

| 市场 | 市场当地时间 | 收盘时间 | 收盘状态 | 今日数据 | 保存范围 |
|------|-------------|---------|---------|---------|---------|
| **CN** | 2026-01-09 12:53 | 15:00 | ❌ 未收盘 | 跳过 | ≤ 2026-01-08 |
| **HK** | 2026-01-09 12:53 | 16:00 | ❌ 未收盘 | 跳过 | ≤ 2026-01-08 |
| **US** | 2026-01-08 23:53 | 16:00 | ✅ 已收盘 | **保存** | ≤ **2026-01-08** |

**优势**: 美股收盘后（16:00 EST）立即可获取当日数据，不用等到第二天，数据及时性提升约10-12小时。

**实现位置**: `download_full_history.py` 的 `save_to_db()` 函数

---

## 📝 八、快速参考

### 常用接口速查

```python
# A股
ak.stock_zh_a_hist()           # 日线
ak.stock_value_em()             # PE/PB/PS等估值
ak.stock_financial_report_sina() # 财报

# 港股  
ak.stock_hk_hist()                  # 日线 (推荐)
fetch_hk_valuation_baidu_direct()   # TTM PE/PB (当前最强推荐)
ft.request_history_kline()          # 日线+静态PE (高质量,需FutuOpenD)
~~ak.stock_hk_indicator_eniu()~~    # 已停更 ❌

# 美股
ak.stock_us_hist()              # 日线
yf.Ticker().history()           # 日线
yf.Ticker().info                # 实时估值
yf.Ticker().financials          # 财报
```

---

**最后更新**: 2026-01-09  
### 6. 指数下载兜底策略 (yfinance Fallback)

在全量下载 (`download_full_history.py`) 中，如果 `yfinance` 出现以下情况，将触发补全机制：

1.  **Period 'max' invalid**: 某些指数（如 `HSTECH.HK`）不支持长周期。此时应调用 `ak.stock_hk_index_daily_sina(symbol="HSTECH")`。
2.  **Possible delisted**: 映射错误（如 A 股指数映射到 `.SZ`）。修复映射后重试。
3.  **数据缺失**: 如果 `yfinance` 因网络或 API 波动返回空数据，支持单标的补抓。

---

## 📅 版本记录
- **v2.3** (2026-01-09): 完善指数下载兜底逻辑（AkShare 补全 HSTECH 历史）。
- **v2.2** (2026-01-09): 添加日线数据保存判断规则（市场收盘时间逻辑）。

---

## 📝 九、接口参数规范详解

### A股接口参数规范

#### 1. `stock_zh_a_hist()` - A股历史K线

**参数说明**:
```python
ak.stock_zh_a_hist(
    symbol="600519",      # 股票代码 (6位数字)
    period="daily",       # 周期: daily/weekly/monthly
    start_date="20200101", # 开始日期 (YYYYMMDD格式,可选)
    end_date="20231231",   # 结束日期 (YYYYMMDD格式,可选)
    adjust="qfq"          # 复权类型: qfq(前复权)/hfq(后复权)/""(不复权)
)
```

**Symbol格式要求**:
- ✅ 正确: `"600519"` (6位纯数字)
- ❌ 错误: `"600519.SS"`, `"SH600519"`

**注意事项**:
- 上海股票: 6开头 (如 600519)
- 深圳主板: 000开头 (如 000858)
- 深圳中小板: 002开头
- 创业板: 300开头
- 科创板: 688开头
- 北交所: 8或4开头

---

#### 2. `stock_value_em()` - A股估值数据

**参数说明**:
```python
ak.stock_value_em(
    symbol="600519"  # 股票代码 (6位数字)
)
```

**Symbol格式要求**:
- ✅ 正确: `"600519"`, `"000858"`, `"300750"`
- ❌ 错误: `"600519.SS"`, `"SH600519"`

**返回字段**:
- 数据日期, 当日收盘价, 当日涨跌幅
- PE(TTM), PE(静), PEG值
- 市净率, 市销率, 市现率
- 总市值, 流通市值, 总股本, 流通股本

---

### 港股接口参数规范

#### 3. `stock_hk_hist()` - 港股历史K线

**参数说明**:
```python
ak.stock_hk_hist(
    symbol="00700",       # 港股代码 (5位数字,前补0)
    period="daily",       # 周期: daily/weekly/monthly
    start_date="20200101", # 开始日期 (YYYYMMDD格式,可选)
    end_date="20231231",   # 结束日期 (YYYYMMDD格式,可选)
    adjust="qfq"          # 复权类型: qfq/hfq/""
)
```

**Symbol格式要求**:
- ✅ 正确: `"00700"`, `"09988"`, `"00005"` (5位数字,前补0)
- ❌ 错误: `"700"`, `"0700.HK"`, `"HK.00700"`

**注意事项**:
- 必须是5位数字
- 不足5位的前面补0
- 例: 腾讯是 `"00700"` 不是 `"700"`

---

#### 4. `stock_hk_indicator_eniu()` - 港股估值指标

**参数说明**:
```python
ak.stock_hk_indicator_eniu(
    symbol="hk00700",    # 港股代码 (hk + 5位数字)
    indicator="市盈率"   # 指标类型
)
```

**Symbol格式要求**:
- ✅ 正确: `"hk00700"`, `"hk09988"`, `"hk00005"`
- ❌ 错误: `"00700"`, `"HK00700"`, `"700"`

**Indicator可选值**:
- `"市盈率"` - 返回: date, pe, price
- `"市净率"` - 返回: date, pb, price
- `"股息率"` - 返回: date, dv, price
- `"ROE"` - 返回: date, roe, expect_roe
- `"市值"` - 返回: date, market_value

**注意事项**:
- symbol必须以小写 `"hk"` 开头
- 后面跟5位数字代码

---

#### 5. `stock_hk_valuation_baidu()` - 港股估值(百度)

**参数说明**:
```python
ak.stock_hk_valuation_baidu(
    symbol="00700",      # 港股代码 (5位数字)
    indicator="市净率",  # 指标类型
    period="近一年"      # 时间周期
)
```

**Symbol格式要求**:
- ✅ 正确: `"00700"`, `"09988"`
- ❌ 错误: `"hk00700"`, `"700"`

**Indicator可选值**:
- `"总市值"` ✅ 可用
- `"市盈率"` ❌ 不可用 (API问题)
- `"市净率"` ✅ 可用
- `"市销率"` ❌ 不可用
- `"市现率"` ✅ 可用
- `"股息率"` ❌ 不可用

**Period可选值**:
- `"近一年"`, `"近三年"`, `"近五年"`, `"全部"`

---

### 美股接口参数规范

#### 6. `stock_us_hist()` - 美股历史K线

**参数说明**:
```python
ak.stock_us_hist(
    symbol="105.AAPL",    # 美股代码 (交易所代码.股票代码)
    period="daily",       # 周期: daily/weekly/monthly
    start_date="20200101", # 开始日期 (YYYYMMDD格式,可选)
    end_date="20231231",   # 结束日期 (YYYYMMDD格式,可选)
    adjust=""             # 复权类型: ""(不复权)
)
```

**Symbol格式要求**:
- ✅ 正确: `"105.AAPL"`, `"105.MSFT"`, `"105.GOOGL"`
- ❌ 错误: `"AAPL"`, `"AAPL.US"`

**交易所代码**:
- `105.` - 纳斯达克/纽交所
- `106.` - 其他交易所

**注意事项**:
- 必须包含交易所前缀
- 格式: `"交易所代码.股票代码"`

---

#### 7. `stock_us_famous_spot_em()` - 美股知名股票实时

**参数说明**:
```python
ak.stock_us_famous_spot_em(
    symbol="科技类"  # 板块类型
)
```

**Symbol可选值**:
- `"科技类"`, `"金融类"`, `"医药食品类"`
- `"媒体类"`, `"汽车能源类"`, `"制造零售类"`

**返回字段**:
- 序号, 名称, 最新价, 涨跌额, 涨跌幅
- 开盘价, 最高价, 最低价, 昨收价
- 总市值, **市盈率**, 代码

**注意事项**:
- 返回的代码格式为: `"105.AAPL"`
- 包含市盈率字段(实时)

---

### yfinance 接口参数规范

#### 8. `yfinance.Ticker()` - 通用接口

**参数说明**:
```python
import yfinance as yf

# 创建Ticker对象
ticker = yf.Ticker("AAPL")  # 美股: 直接使用代码
ticker = yf.Ticker("0700.HK")  # 港股: 代码.HK
ticker = yf.Ticker("600519.SS")  # A股: 代码.SS/SZ

# 获取历史数据
df = ticker.history(
    period="1y",      # 时间范围: 1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max
    interval="1d",    # 数据间隔: 1m/2m/5m/15m/30m/60m/90m/1d/5d/1wk/1mo/3mo
    start="2020-01-01",  # 开始日期 (可选)
    end="2023-12-31"     # 结束日期 (可选)
)
```

**Symbol格式要求**:

**美股**:
- ✅ 正确: `"AAPL"`, `"MSFT"`, `"GOOGL"`
- ❌ 错误: `"105.AAPL"`

**港股**:
- ✅ 正确: `"0700.HK"`, `"9988.HK"`, `"0005.HK"`
- ❌ 错误: `"00700.HK"`, `"HK.0700"`
- 注意: 去掉前导0,只保留有效数字

**A股**:
- 上海: `"600519.SS"`, `"688001.SS"`
- 深圳: `"000858.SZ"`, `"300750.SZ"`
- 北京: `"430047.BJ"`

---

### Futu API 接口参数规范

#### 9. `request_history_kline()` - Futu历史K线

**参数说明**:
```python
import futu as ft

quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)

ret, data, page_req_key = quote_ctx.request_history_kline(
    code='HK.00700',           # 股票代码 (市场.代码)
    start='2025-01-01',        # 开始日期 (YYYY-MM-DD)
    end='2026-01-08',          # 结束日期 (YYYY-MM-DD)
    ktype=ft.KLType.K_DAY,     # K线类型
    autype=ft.AuType.QFQ,      # 复权类型
    max_count=1000             # 最大返回条数
)
```

**Code格式要求**:

**港股**:
- ✅ 正确: `"HK.00700"`, `"HK.09988"`, `"HK.00005"`
- ❌ 错误: `"00700"`, `"0700.HK"`
- 格式: `"HK." + 5位数字代码`

**A股**:
- 上海: `"SH.600519"`, `"SH.688001"`
- 深圳: `"SZ.000858"`, `"SZ.300750"`

**美股**:
- ✅ 正确: `"US.AAPL"`, `"US.MSFT"`

**KLType可选值**:
- `ft.KLType.K_DAY` - 日K线
- `ft.KLType.K_WEEK` - 周K线
- `ft.KLType.K_MON` - 月K线
- `ft.KLType.K_1M` - 1分钟
- `ft.KLType.K_5M` - 5分钟
- `ft.KLType.K_15M` - 15分钟
- `ft.KLType.K_30M` - 30分钟
- `ft.KLType.K_60M` - 60分钟

**AuType可选值**:
- `ft.AuType.QFQ` - 前复权
- `ft.AuType.HFQ` - 后复权
- `ft.AuType.NONE` - 不复权

**返回字段**:
- code, name, time_key
- open, close, high, low
- **pe_ratio**, turnover_rate
- volume, turnover
- change_rate, last_close

---

## 🔍 十、Symbol格式快速对照表

| 数据源 | A股 | 港股 | 美股 |
|--------|-----|------|------|
| **AkShare K线** | `"600519"` | `"00700"` | `"105.AAPL"` |
| **AkShare 估值** | `"600519"` | `"hk00700"` | - |
| **yfinance** | `"600519.SS"` | `"0700.HK"` | `"AAPL"` |
| **Futu API** | `"SH.600519"` | `"HK.00700"` | `"US.AAPL"` |

### 注意事项

1. **不同接口对同一股票的代码格式要求不同**
2. **调用前必须按照接口要求转换格式**
3. **港股代码位数要求**:
   - AkShare: 5位 (`"00700"`)
   - yfinance: 去前导0 (`"0700.HK"`)
   - Futu: 5位 (`"HK.00700"`)
4. **大小写敏感**:
   - `"hk00700"` ≠ `"HK00700"`
   - 严格按照文档要求

---

**最后更新**: 2026-01-08  
**文档版本**: v2.2

---

## 📦 十一、ETF 参数规范

### ETF与个股的区别

**数据获取方式**: ETF使用与个股相同的接口,但需要注意:
- **内部标识**: 使用 `asset_type='ETF'` 区分
- **Symbol格式**: 与个股相同
- **数据字段**: 完全相同

### 美股ETF

**常见ETF代码**:
```python
# 指数ETF
'SPY'   # 标普500指数ETF
'QQQ'   # 纳指100ETF
'DIA'   # 道琼斯指数ETF
'IWM'   # 罗素2000指数ETF

# 债券ETF
'TLT'   # 20年期以上国债ETF
'SGOV'  # 0-3月美国国债ETF

# 行业ETF
'XLK'   # 科技行业ETF
'XLF'   # 金融行业ETF
'XLE'   # 能源指数ETF
```

**数据获取**:
```python
# yfinance (推荐)
import yfinance as yf
ticker = yf.Ticker("SPY")  # 直接使用代码
df = ticker.history(period="1y")

# AkShare
import akshare as ak
df = ak.stock_us_hist(symbol="105.SPY", period="daily")  # 需要交易所前缀
```

### A股ETF

**ETF代码规律**:
- `159XXX`: 深圳ETF
- `510XXX`, `512XXX`, `513XXX`, `515XXX`, `516XXX`, `517XXX`, `588XXX`: 上海ETF

**示例**:
```python
'159662'  # 航运ETF
'159751'  # 港股通科技ETF
'510300'  # 沪深300ETF
```

**数据获取**:
```python
# AkShare (推荐)
import akshare as ak
df = ak.stock_zh_a_hist(symbol="159662", period="daily", adjust="qfq")

# yfinance
import yfinance as yf
ticker = yf.Ticker("159662.SZ")  # 深圳ETF用.SZ
```

### 港股ETF

**ETF代码规律**:
- `28XX`, `30XX`, `31XX`

**示例**:
```python
'02800'  # 盈富基金(追踪恒生指数)
'03033'  # 南方A50ETF
'03110'  # 恒生科技ETF
```

**数据获取**:
```python
# AkShare (推荐)
import akshare as ak
df = ak.stock_hk_hist(symbol="02800", period="daily", adjust="qfq")

# yfinance
import yfinance as yf
ticker = yf.Ticker("2800.HK")  # 去前导0
```

---

## 📊 十二、指数 (Index) 参数规范

### 美股指数

**支持的指数** (来自 `symbols_config.py`):

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `^DJI` | `^DJI` | `.DJI` | 道琼斯工业指数 |
| `^NDX` | `^NDX` | `.NDX` | 纳斯达克100指数 |
| `^SPX` | `^GSPC` | `.INX` | 标普500指数 |

**⚠️ 重要映射**:
- `^SPX` 在 yfinance 中是 `^GSPC`
- AkShare 使用 `.` 前缀 (如 `.DJI`, `.NDX`, `.INX`)

**数据获取**:
```python
# yfinance (推荐)
import yfinance as yf
from backend.symbols_config import get_yfinance_symbol

# 方法1: 直接使用
ticker = yf.Ticker("^DJI")

# 方法2: 使用映射函数
yf_symbol = get_yfinance_symbol("^SPX")  # 返回 "^GSPC"
ticker = yf.Ticker(yf_symbol)

# AkShare
import akshare as ak
from backend.symbols_config import get_akshare_symbol

ak_symbol = get_akshare_symbol("^DJI")  # 返回 ".DJI"
df = ak.stock_us_hist(symbol=ak_symbol, period="daily")
```

### 港股指数

**支持的指数**:

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `HSI` | `^HSI` | `800000` | 恒生指数 |
| `HSTECH` | `HSTECH.HK` | `800700` | 恒生科技指数 |

**⚠️ 重要映射**:
- AkShare 港股指数使用特殊代码 (`800000`, `800700`)
- 必须通过 `symbols_config.py` 的映射函数转换

**数据获取**:
```python
# yfinance
import yfinance as yf
ticker = yf.Ticker("^HSI")  # 恒生指数
ticker = yf.Ticker("HSTECH.HK")  # 恒生科技

# AkShare (需要映射)
import akshare as ak
from backend.symbols_config import get_akshare_symbol

ak_symbol = get_akshare_symbol("HSI")  # 返回 "800000"
df = ak.stock_hk_hist(symbol=ak_symbol, period="daily")
```

### A股指数

**支持的指数**:

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `000001.SS` | `000001.SS` | `sh000001` | 上证综合指数 |

**⚠️ 重要区分**:
- `000001` = 平安银行 (股票)
- `sh000001` = 上证指数 (指数)
- 必须使用 `sh` 前缀

**数据获取**:
```python
# yfinance
import yfinance as yf
ticker = yf.Ticker("000001.SS")

# AkShare (需要映射)
import akshare as ak
from backend.symbols_config import get_akshare_symbol

ak_symbol = get_akshare_symbol("000001.SS")  # 返回 "sh000001"
df = ak.stock_zh_index_hist(symbol=ak_symbol)
```

---

## 🔑 十三、asset_type 识别规则

### 三种资产类型

| asset_type | 说明 | Canonical ID示例 |
|-----------|------|-----------------|
| `STOCK` | 普通股票 | `US:STOCK:AAPL` |
| `ETF` | 交易所交易基金 | `US:ETF:SPY` |
| `INDEX` | 市场指数 | `US:INDEX:^DJI` |

### 识别规则代码

**美股**:
```python
def identify_us_asset_type(symbol: str) -> str:
    # 指数: 以 ^ 开头
    if symbol.startswith('^'):
        return 'INDEX'
    
    # ETF: 已知ETF列表
    known_etfs = ['SPY', 'QQQ', 'TLT', 'DIA', 'IWM', 'XLK', 'XLF', ...]
    if symbol in known_etfs:
        return 'ETF'
    
    # 默认: 股票
    return 'STOCK'
```

**A股**:
```python
def identify_cn_asset_type(symbol: str) -> str:
    # 指数: sh/sz 前缀
    if symbol.startswith('sh') or symbol.startswith('sz'):
        return 'INDEX'
    
    # ETF: 特定代码段
    if symbol.startswith(('159', '510', '512', '513', '515', '516', '517', '588')):
        return 'ETF'
    
    # 默认: 股票
    return 'STOCK'
```

**港股**:
```python
def identify_hk_asset_type(symbol: str) -> str:
    # 指数: 已知指数代码
    if symbol in ['HSI', 'HSTECH']:
        return 'INDEX'
    
    # ETF: 28XX, 30XX, 31XX
    if symbol.startswith(('28', '30', '31')):
        return 'ETF'
    
    # 默认: 股票
    return 'STOCK'
```

---

## 📋 十四、完整数据获取示例

### 示例1: 美股ETF (SPY)

```python
import yfinance as yf
import akshare as ak

# 1. yfinance (推荐)
ticker = yf.Ticker("SPY")
df_kline = ticker.history(period="1y")
pe = ticker.info.get('trailingPE')

# 2. AkShare
df_kline = ak.stock_us_hist(symbol="105.SPY", period="daily")
```

### 示例2: 港股指数 (HSI)

```python
import yfinance as yf
import akshare as ak
from backend.symbols_config import get_yfinance_symbol, get_akshare_symbol

# 1. yfinance
yf_symbol = get_yfinance_symbol("HSI")  # 返回 "^HSI"
ticker = yf.Ticker(yf_symbol)
df = ticker.history(period="1y")

# 2. AkShare
ak_symbol = get_akshare_symbol("HSI")  # 返回 "800000"
df = ak.stock_hk_hist(symbol=ak_symbol, period="daily")
```

### 示例3: A股ETF (159662)

```python
import yfinance as yf
import akshare as ak

# 1. AkShare (推荐)
df = ak.stock_zh_a_hist(symbol="159662", period="daily", adjust="qfq")

# 2. yfinance
ticker = yf.Ticker("159662.SZ")
df = ticker.history(period="1y")
```

---

**最后更新**: 2026-01-08  
**文档版本**: v2.2
