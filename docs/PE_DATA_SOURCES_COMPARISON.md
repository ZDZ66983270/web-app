# PE 数据源完整对比表

## 测试日期
2026-01-08

## 测试目标
验证各数据源的历史K线和实时数据中是否包含 PE 比率(市盈率)

---

## 📊 完整对比表

| 数据源 | 接口名称 | 接口类型 | 美股 | 港股 | A股 | 备注 |
|--------|---------|---------|------|------|-----|------|
| **yfinance** | `ticker.history()` | 历史K线 | ❌ | ❌ | ❌ | 只有OHLCV数据 |
| **yfinance** | `ticker.info` | 实时快照 | ✅ | ✅ | ✅ | trailingPE, forwardPE |
| **AkShare** | `stock_us_hist()` | 美股历史K线 | ❌ | - | - | 只有OHLCV数据 |
| **AkShare** | `stock_us_famous_spot_em()` | 美股实时快照 | ✅ | - | - | 包含"市盈率"字段 |
| **AkShare** | `stock_hk_hist()` | 港股历史K线 | - | ❌ | - | 只有OHLCV数据 |
| **AkShare** | `stock_hk_spot_em()` | 港股实时快照 | - | ❌ | - | 不包含PE字段 |
| **AkShare** | `stock_zh_a_hist()` | A股历史K线 | - | - | ❌ | 只有OHLCV数据 |
| **AkShare** | `stock_zh_a_spot_em()` | A股实时快照 | - | - | ✅ | 包含"市盈率-动态"字段 |
| **Futu API** | `request_history_kline()` | 港股历史K线 | ❓ | ✅ | ❓ | **包含pe_ratio字段,100%可用** |
| **Futu API** | 实时行情 | 实时快照 | ❓ | ✅ | ❓ | 包含PE数据 |

**图例**:
- ✅ = 包含PE数据
- ❌ = 不包含PE数据
- ❓ = 未测试
- `-` = 不适用

---

## 📝 详细测试结果

### 1. yfinance

#### 历史K线 (`ticker.history()`)
```python
import yfinance as yf
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="3mo")
# 返回字段: ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
# ❌ 不包含 PE
```

#### 实时快照 (`ticker.info`)
```python
info = ticker.info
# ✅ 包含: info['trailingPE'], info['forwardPE']
```

**适用市场**: 美股、港股、A股
**PE可用性**: 仅实时快照有PE,历史K线无PE

---

### 2. AkShare

#### 美股历史K线 (`stock_us_hist()`)
```python
import akshare as ak
df = ak.stock_us_hist(symbol="105.AAPL", period="daily")
# 返回字段: ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
# ❌ 不包含 PE
```

#### 美股实时快照 (`stock_us_famous_spot_em()`)
```python
df = ak.stock_us_famous_spot_em(symbol='科技类')
# 返回字段: ['序号', '名称', '最新价', '涨跌额', '涨跌幅', '开盘价', '最高价', '最低价', '昨收价', '总市值', '市盈率', '代码']
# ✅ 包含 '市盈率' 字段
```

#### 港股历史K线 (`stock_hk_hist()`)
```python
df = ak.stock_hk_hist(symbol="00700", period="daily", adjust="qfq")
# 返回字段: ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
# ❌ 不包含 PE
```

#### 港股实时快照 (`stock_hk_spot_em()`)
```python
df = ak.stock_hk_spot_em()
# 返回字段: ['序号', '代码', '名称', '最新价', '涨跌额', '涨跌幅', '今开', '最高', '最低', '昨收', '成交量', '成交额']
# ❌ 不包含 PE 字段
```

#### A股历史K线 (`stock_zh_a_hist()`)
```python
df = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="qfq")
# 返回字段: ['日期', '股票代码', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
# ❌ 不包含 PE
```

#### A股实时快照 (`stock_zh_a_spot_em()`)
```python
df = ak.stock_zh_a_spot_em()
# 返回字段: ['序号', '代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '振幅', '最高', '最低', '今开', '昨收', '量比', '换手率', '市盈率-动态', '市净率', '总市值', '流通市值', ...]
# ✅ 包含 '市盈率-动态' 字段
```

**适用市场**: 美股、港股、A股
**PE可用性**: 
- 美股: 实时快照有PE ✅
- 港股: 实时快照无PE ❌
- A股: 实时快照有PE ✅
- 所有历史K线都无PE ❌

---

### 3. Futu API

#### 港股历史K线 (`request_history_kline()`)
```python
import futu as ft
quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
ret, data, page_req_key = quote_ctx.request_history_kline(
    code='HK.09988',
    start='2025-10-10',
    end='2026-01-08',
    ktype=ft.KLType.K_DAY,
    autype=ft.AuType.QFQ
)
# 返回字段: ['code', 'name', 'time_key', 'open', 'close', 'high', 'low', 'pe_ratio', 'turnover_rate', 'volume', 'turnover', 'change_rate', 'last_close']
# ✅ 包含 'pe_ratio' 字段,100% 数据完整
```

**测试结果**:
- 09988 (阿里巴巴): 61条数据, PE有效率 100%
- 00005 (汇丰控股): 61条数据, PE有效率 100%

**适用市场**: 港股(已测试), 美股/A股(未测试)
**PE可用性**: ✅ **历史K线包含每日PE,唯一提供此功能的免费数据源**

---

## 🎯 结论与建议

### 历史每日PE数据获取方案

#### 港股 ⭐⭐⭐⭐
**推荐**: Futu API
- ✅ 历史K线直接包含 pe_ratio
- ✅ 数据完整性 100%
- ✅ 免费使用(需下载 FutuOpenD)

#### 美股 ⭐⭐
**方案A**: 自行计算
```python
PE = Price / EPS
# Price: yfinance.history() 或 akshare.stock_us_hist()
# EPS: yfinance.info['trailingEps'] 或财报数据
```

**方案B**: 定期记录实时PE
```python
# 每日记录 yfinance.info['trailingPE'] 或 akshare.stock_us_famous_spot_em()
```

#### A股 ⭐⭐
**方案A**: 自行计算
```python
PE = Price / EPS
# Price: akshare.stock_zh_a_hist()
# EPS: 从财报数据计算
```

**方案B**: 定期记录实时PE
```python
# 每日记录 akshare.stock_zh_a_spot_em() 的 '市盈率-动态'
```

---

## 📌 关键发现

1. **所有数据源的历史K线接口都不包含PE** (除了 Futu API 港股)
2. **实时快照接口通常包含PE** (但这不是历史数据)
3. **Futu API 是唯一提供历史每日PE的免费数据源**
4. 如需历史PE,必须:
   - 使用 Futu API (港股)
   - 自行计算 (美股/A股)
   - 定期记录实时PE值

---

## 🔗 相关测试脚本

- `test_yfinance_us_pe.py` - yfinance 美股PE测试
- `test_yahoo_akshare_pe.py` - Yahoo/AkShare 对比测试
- `test_akshare_us_hist.py` - AkShare 美股历史数据测试
- `test_futu_hk_kline.py` - Futu API 港股测试

---

**最后更新**: 2026-01-08
**测试环境**: macOS, Python 3.13
