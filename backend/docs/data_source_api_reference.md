# 数据源接口完整文档

## 📋 概述

本文档详细记录了系统使用的各数据源对三个市场（CN、HK、US）的指数和个股的接口格式、参数以及限制。

---

## 🇨🇳 CN市场（中国A股）

### 数据源：AkShare

#### 1. CN指数 - 日线数据

**接口**: `ak.stock_zh_index_daily()`

**参数**:
```python
symbol: str  # 指数代码（AkShare格式）
```

**代码映射**:
| 标准代码 | AkShare代码 | 名称 |
|---------|------------|------|
| 000001.SS | sh000001 | 上证指数 |
| 399001.SZ | sz399001 | 深证成指 |
| 399006.SZ | sz399006 | 创业板指 |

**返回字段**:
```python
{
    'date': str,        # 日期 '2025-12-18'
    'open': float,      # 开盘价
    'close': float,     # 收盘价
    'high': float,      # 最高价
    'low': float,       # 最低价
    'volume': float,    # 成交量
    'amount': float,    # 成交额
    'amplitude': float, # 振幅
    'change_pct': float,# 涨跌幅
    'change': float,    # 涨跌额
    'turnover': float   # 换手率
}
```

**限制**:
- ❌ 不支持天数限制
- ✅ 总是返回所有历史数据
- ✅ 数据从指数成立日开始
- ⚠️ 字段名为中文

**示例**:
```python
import akshare as ak

df = ak.stock_zh_index_daily(symbol="sh000001")
# 返回: 8546条记录 (1990-12-19 至今)
```

---

#### 2. CN个股 - 日线数据

**接口**: `ak.stock_zh_a_hist()`

**参数**:
```python
symbol: str      # 股票代码（6位数字）
period: str      # 周期 "daily", "weekly", "monthly"
start_date: str  # 开始日期 "20200101" (可选)
end_date: str    # 结束日期 "20251218" (可选)
adjust: str      # 复权类型 "" (不复权), "qfq" (前复权), "hfq" (后复权)
```

**代码格式**:
| 标准代码 | AkShare代码 | 说明 |
|---------|------------|------|
| 600519.SS | 600519 | 只需6位数字 |
| 000001.SZ | 000001 | 只需6位数字 |

**返回字段**:
```python
{
    '日期': str,      # '2025-12-18'
    '开盘': float,
    '收盘': float,
    '最高': float,
    '最低': float,
    '成交量': float,
    '成交额': float,
    '振幅': float,
    '涨跌幅': float,
    '涨跌额': float,
    '换手率': float
}
```

**限制**:
- ❌ 不支持天数限制（除非用start_date/end_date）
- ✅ 默认返回所有历史
- ✅ 支持日期范围筛选
- ⚠️ 字段名为中文

**示例**:
```python
# 全量下载
df = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="")
# 返回: 5825条记录 (2001-08-27 至今)

# 指定日期范围
df = ak.stock_zh_a_hist(
    symbol="600519", 
    period="daily",
    start_date="20250101",
    end_date="20251218",
    adjust=""
)
```

---

#### 3. CN个股 - 分钟数据

**接口**: `ak.stock_zh_a_hist_min_em()`

**参数**:
```python
symbol: str   # 股票代码（6位数字）
period: str   # 周期 "1", "5", "15", "30", "60"
adjust: str   # 复权类型 "" 或 "qfq" 或 "hfq"
start_date: str  # 开始日期时间 "2025-12-18 09:30:00"
end_date: str    # 结束日期时间 "2025-12-18 15:00:00"
```

**返回字段**:
```python
{
    '时间': str,     # '2025-12-18 09:31:00'
    '开盘': float,
    '收盘': float,
    '最高': float,
    '最低': float,
    '成交量': float,
    '成交额': float
}
```

**限制**:
- ⚠️ 只返回最近几天的数据（约5-10天）
- ✅ 支持日期时间范围
- ⚠️ 字段名为中文

---

## 🇭🇰 HK市场（香港股市）

### 数据源：AkShare + yfinance

#### 1. HK指数 - 日线数据

**接口**: `ak.stock_hk_index_daily_sina()`

**参数**:
```python
symbol: str  # 指数代码
```

**代码映射**:
| 标准代码 | AkShare代码 | 名称 |
|---------|------------|------|
| HSI | HSI | 恒生指数 |
| HSTECH | HSTECH | 恒生科技指数 |

**返回字段**:
```python
{
    'date': str,     # '2025-12-18'
    'open': float,
    'high': float,
    'low': float,
    'close': float,
    'volume': float
}
```

**限制**:
- ❌ 不支持天数限制
- ✅ 返回所有历史数据
- ⚠️ 部分指数历史较短

**示例**:
```python
df = ak.stock_hk_index_daily_sina(symbol="HSI")
# 返回: 所有历史数据
```

---

#### 2. HK个股 - 日线数据

**接口**: `ak.stock_hk_daily()`

**参数**:
```python
symbol: str   # 股票代码（5位数字）
adjust: str   # 复权类型 "" 或 "qfq" 或 "hfq"
```

**代码格式**:
| 标准代码 | AkShare代码 | 说明 |
|---------|------------|------|
| 09988.HK | 09988 | 5位数字 |
| 00700.HK | 00700 | 5位数字 |

**返回字段**:
```python
{
    'date': str,
    'open': float,
    'high': float,
    'low': float,
    'close': float,
    'volume': float,
    'turnover': float
}
```

**限制**:
- ❌ 不支持天数限制
- ✅ 返回所有历史数据

**示例**:
```python
df = ak.stock_hk_daily(symbol="09988", adjust="")
```

---

#### 3. HK市场 - yfinance备用

**接口**: `yf.Ticker().history()`

**参数**:
```python
period: str      # "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
interval: str    # "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"
start: str       # "2020-01-01"
end: str         # "2025-12-18"
```

**代码格式**:
| 标准代码 | yfinance代码 | 说明 |
|---------|-------------|------|
| 09988.HK | 9988.HK | 去掉前导0 |
| 00700.HK | 0700.HK | 保留一个0 |

**返回字段**:
```python
{
    'Open': float,
    'High': float,
    'Low': float,
    'Close': float,
    'Volume': int,
    'Dividends': float,
    'Stock Splits': float
}
```

**限制**:
- ✅ 支持period参数
- ✅ 支持日期范围
- ✅ 灵活控制

---

## 🇺🇸 US市场（美国股市）

### 数据源：yfinance

#### 1. US指数 - 日线数据

**接口**: `yf.Ticker().history()`

**参数**:
```python
period: str      # "max" 或其他
interval: str    # "1d"
start: str       # 开始日期
end: str         # 结束日期
```

**代码映射**:
| 标准代码 | yfinance代码 | 名称 |
|---------|-------------|------|
| ^DJI | ^DJI | 道琼斯指数 |
| ^NDX | ^NDX | 纳斯达克100 |
| ^SPX | ^SPX | 标普500 |

**返回字段**:
```python
{
    'Open': float,
    'High': float,
    'Low': float,
    'Close': float,
    'Volume': int,
    'Dividends': float,
    'Stock Splits': float
}
```

**限制**:
- ✅ 支持period参数
- ✅ 支持日期范围
- ✅ 数据完整可靠

**示例**:
```python
import yfinance as yf

# 全量下载
ticker = yf.Ticker("^SPX")
df = ticker.history(period="max")
# 返回: 所有历史数据

# 指定范围
df = ticker.history(period="1y")  # 最近1年
df = ticker.history(start="2020-01-01", end="2025-12-18")
```

---

#### 2. US个股 - 日线数据

**接口**: `yf.Ticker().history()`

**参数**: 同US指数

**代码格式**:
| 标准代码 | yfinance代码 | 说明 |
|---------|-------------|------|
| AAPL | AAPL | 直接使用 |
| MSFT | MSFT | 直接使用 |
| TSLA | TSLA | 直接使用 |

**返回字段**: 同US指数

**限制**: 同US指数

**示例**:
```python
ticker = yf.Ticker("AAPL")
df = ticker.history(period="max")
# 返回: 11346条记录 (1980-12-12 至今)
```

---

#### 3. US市场 - 分钟数据

**接口**: `yf.Ticker().history()`

**参数**:
```python
period: str      # "1d", "5d", "1mo" (分钟数据有限制)
interval: str    # "1m", "5m", "15m", "30m", "60m"
```

**限制**:
- ⚠️ 1分钟数据：最多7天
- ⚠️ 5分钟数据：最多60天
- ⚠️ 15分钟数据：最多60天
- ⚠️ 30分钟数据：最多60天
- ⚠️ 60分钟数据：最多730天

**示例**:
```python
ticker = yf.Ticker("AAPL")
df = ticker.history(period="1d", interval="1m")
# 返回: 当天的1分钟数据
```

---

## 📊 数据源对比总结

### 天数限制能力

| 数据源 | 市场 | 支持天数限制 | 方式 |
|--------|------|-------------|------|
| AkShare | CN指数 | ❌ | 总是全量 |
| AkShare | CN个股 | ⚠️ | 可用start_date/end_date |
| AkShare | HK指数 | ❌ | 总是全量 |
| AkShare | HK个股 | ❌ | 总是全量 |
| yfinance | HK | ✅ | period参数 |
| yfinance | US | ✅ | period参数 |

### 字段名格式

| 数据源 | 字段名语言 | 需要转换 |
|--------|-----------|---------|
| AkShare CN | 中文 | ✅ 需要 |
| AkShare HK | 英文 | ❌ 不需要 |
| yfinance | 英文 | ❌ 不需要 |

### 数据完整性

| 数据源 | 历史深度 | 数据质量 |
|--------|---------|---------|
| AkShare CN | ✅ 完整 | ✅ 优秀 |
| AkShare HK | ⚠️ 部分 | ✅ 良好 |
| yfinance US | ✅ 完整 | ✅ 优秀 |
| yfinance HK | ✅ 完整 | ✅ 优秀 |

---

## 🔧 系统实现策略

### 统一处理流程

```python
def fetch_xxx_daily_data(symbol: str) -> pd.DataFrame:
    """
    1. 调用数据源API（总是获取全量或最大范围）
    2. 标准化字段名（中文→英文）
    3. 标准化日期格式
    4. 返回DataFrame
    """
    
def backfill_missing_data(symbol: str, market: str, days: int = None):
    """
    1. 调用fetch_xxx_daily_data获取全量
    2. 如果days不为None，使用tail(days)限制
    3. 保存到RawMarketData
    4. 触发ETL处理
    """
```

### 优势

1. **统一接口**: 所有市场使用相同逻辑
2. **简单可靠**: 在Python层面处理限制
3. **灵活控制**: 支持全量和限制两种模式

---

## 📋 使用示例

### 全量下载新股票

```python
from data_fetcher import DataFetcher

fetcher = DataFetcher()

# 自动检测：新股票全量下载
result = fetcher.backfill_missing_data('AAPL', 'US', days=None)
# 下载: 11000+条记录（1980至今）
```

### 回填缺失数据

```python
# 自动检测：有数据的股票只回填缺失
result = fetcher.backfill_missing_data('000001.SS', 'CN', days=None)
# 智能判断: 缺失3天→回填8天
```

### 手动指定天数

```python
# 强制回填30天
result = fetcher.backfill_missing_data('HSI', 'HK', days=30)
# 下载: 最近30天数据
```

---

## ⚠️ 注意事项

### AkShare

1. **中文字段名**: 需要转换为英文
2. **无天数限制**: 总是返回全量，需代码限制
3. **代理问题**: 需禁用系统代理
4. **速率限制**: 频繁调用可能被限制

### yfinance

1. **时区问题**: 返回带时区的时间戳
2. **分钟数据限制**: 不同周期有不同的历史深度限制
3. **网络依赖**: 需要稳定的国际网络
4. **字段名大小写**: 首字母大写

---

## 🎯 最佳实践

1. **新股票**: 使用`days=None`全量下载
2. **数据维护**: 使用自动检测模式
3. **手动回填**: 根据需要指定天数
4. **错误处理**: 捕获网络和API异常
5. **日志记录**: 记录下载进度和结果

---

## 📈 财务基本面数据 (Financial Fundamentals)

基本面数据（营收、利润、现金流、资产负债）采用独立的数据源策略，以支持深度基本面分析。

### 1. CN市场 (A股)

**数据源**: AkShare (新浪财经接口)

**接口**: `ak.stock_financial_abstract()`

**参数**:
```python
symbol: str  # 股票代码 (6位数字，如 "600519")
```

**字段映射**:
| 内部字段 | AkShare指标 | 说明 |
|---------|------------|------|
| revenue_ttm | 营业总收入 | 自动扩展为元 |
| net_income_ttm | 归母净利润 | 归属于母公司股东的净利润 |
| operating_cashflow_ttm | 经营现金流量净额 | |
| total_assets | (推算) | 基于 净资产 / (1 - 资产负债率) |
| total_liabilities | (推算) | 基于 总资产 * 资产负债率 |

---

### 2. HK市场 (港股)

**数据源**: AkShare (东方财富) + yfinance

**接口 A**: `ak.stock_financial_hk_analysis_indicator_em()` (年度数据)

**参数**:
```python
symbol: str      # 股票代码 (5位数字，如 "00700")
indicator: str   # "年度"
```

**接口 B**: `yf.Ticker().quarterly_financials` (季度数据)
*   用于补充最近季度的财务状况。

---

### 3. US市场 (美股)

**数据源**: yfinance

**接口**:
*   `ticker.financials` (年度利润表)
*   `ticker.balance_sheet` (年度资产负债表)
*   `ticker.cashflow` (年度现金流表)
*   `ticker.quarterly_xxx` (季度数据)

**参数**:
*   直接通过 Ticker 对象访问属性，无需额外参数。

**关键指标**:
*   `Total Revenue` -> `revenue_ttm`
*   `Net Income` -> `net_income_ttm`
*   `Operating Cash Flow` -> `operating_cashflow_ttm`
*   `Total Assets` -> `total_assets`

---

## 💰 估值指标 (Valuation Metrics)

系统针对不同市场采用差异化的估值数据获取策略。

### 1. CN市场 (A股) - 历史直接获取
*   **接口**: `ak.stock_value_em(symbol)`
*   **来源**: 东方财富
*   **内容**: 获取完整的历史 **PE-TTM** 和 **PB** 数据序列。
*   **处理**: 直接将历史估值数据回填到 `MarketDataDaily` 表中对应的每一个交易日。

### 2. HK市场 (港股) - 历史直接获取
*   **接口**: 百度股市通 OpenData API (`gushitong.baidu.com`)
*   **内容**: 获取完整的历史 **PE-TTM** 和 **PB** 数据序列。
*   **处理**: 解析百度 API 返回的 JSON，回填到 `MarketDataDaily`。

### 3. US市场 (美股) - 快照 + 历史
*   **当前快照 (Real-time)**:
    *   **接口**: `yf.Ticker().info`
    *   **内容**: 获取 **当前最新** 的 `trailingPE` (PE-TTM), `priceToBook`, `dividendYield`。
*   **历史数据 (Historical)**:
    *   **接口**: FMP Cloud (`/stable/ratios`)
    *   **内容**: 获取 **历年年报/季报** 的 PE (`priceToEarningsRatio`) 和 PB (`priceToBookRatio`)。
    *   **处理**: 将历史 PE/PB 序列回填到 `MarketDataDaily` 的对应日期，补全历史走势。

### 4. 股息率 (Dividend Yield)
*   **CN**: 基于 `ak.stock_fhps_detail_em` 获取完整的**分红派息记录**，结合当前股价得出 (因实时接口暂缺字段)。
*   **HK**: 直接获取 `yf.Ticker().info['dividendYield']` (System Fetch)。
*   **US**: 直接获取 `yf.Ticker().info['dividendYield']` (System Fetch)。
