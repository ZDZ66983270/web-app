# AkShare 股息率获取方式分析

根据 AkShare 文档分析,找到以下股息率获取接口:

## 1. A股股息率 (整体市场)

### 接口
```python
import akshare as ak
stock_a_gxl_lg_df = ak.stock_a_gxl_lg(symbol="上证A股")
```

### 说明
- **数据源**: 乐咕乐股 (https://legulegu.com/stockdata/guxilv)
- **数据类型**: 市场整体股息率(非个股)
- **支持市场**: 上证A股、深证A股等
- **数据格式**: 时间序列数据
- **限制**: 返回的是**市场整体股息率**,不是个股股息率

### 数据示例
```
日期          股息率
2005-01-04   2.03
2005-01-05   2.05
...
2024-04-24   3.50
```

---

## 2. 港股分红派息

### 接口
```python
import akshare as ak
stock_hk_dividend_payout_em_df = ak.stock_hk_dividend_payout_em(symbol="03900")
```

### 说明
- **数据源**: 东方财富-港股
- **数据类型**: 个股分红派息记录
- **返回内容**: 
  - 最新公告日期
  - 财政年度
  - 每股派息(港元)
  - 除净日
  - 截至过户日
  - 发放日

### 数据示例
```
最新公告日期  财政年度  每股派息  除净日      发放日
2025-06-20   2024    0.328   2025/06/26  2025-07-31
```

---

## 3. 港股财务指标 (含股息率)

### 接口
```python
import akshare as ak
stock_hk_financial_indicator_em_df = ak.stock_hk_financial_indicator_em(symbol="03900")
```

### 说明
- **数据源**: 东方财富-港股-核心必读-最新指标
- **包含字段**: 
  - **每股股息TTM(港元)** ✅
  - **派息比率(%)** ✅
  - 基本每股收益
  - 每股净资产
  - 市盈率、市净率等

### 数据示例
```
每股股息TTM(港元)  派息比率(%)
0.328            -322.18
```

---

## 4. A股历史分红 (个股)

### 接口
```python
import akshare as ak
stock_dividend_cninfo_df = ak.stock_dividend_cninfo(symbol="600009")
```

### 说明
- **数据源**: 巨潮资讯
- **数据类型**: 个股历史分红记录
- **返回内容**:
  - 实施方案公告日期
  - 分红类型(年度/中期)
  - 送股比例、转增比例
  - **派息比例** (如: 10派3元)
  - 派息日、股份到账日

### 数据示例
```
实施方案公告日期  分红类型  派息比例
2025-08-04      年度分红  10派3元(含税)
2024-07-15      年度分红  10派1.2元(含税)
```

---

## 总结与建议

### 可用接口汇总

| 市场 | 接口函数 | 数据类型 | 是否包含股息率 | 数据来源 |
|------|---------|---------|--------------|---------|
| **A股(市场)** | `stock_a_gxl_lg()` | 市场整体股息率 | ✅ 直接提供 | 乐咕乐股 |
| **A股(个股)** | `stock_dividend_cninfo()` | 历史分红记录 | ❌ 需计算 | 巨潮资讯 |
| **A股(个股)** | `stock_fhps_em()` | 分红配送 | ❌ 需计算 | 东方财富 |
| **A股(个股)** | `stock_fhps_detail_em()` | 分红配送详情 | ❌ 需计算 | 东方财富 |
| **A股(个股)** | `stock_fhps_detail_ths()` | 分红情况 | ✅ 税前分红率 | 同花顺 |
| **A股(个股)** | `news_trade_notify_dividend_baidu()` | 分红派息提醒 | ❌ 需计算 | 百度股市通 |
| **港股(个股)** | `stock_hk_financial_indicator_em()` | 财务指标 | ✅ TTM股息 | 东方财富 |
| **港股(个股)** | `stock_hk_dividend_payout_em()` | 分红派息记录 | ❌ 需计算 | 东方财富 |

### 新发现的接口详解

#### 1. 分红配送-东财 (A股)
```python
import akshare as ak
df = ak.stock_fhps_em(date="20231231")
```
- **说明**: 获取指定日期的所有A股分红配送数据
- **字段**: 送转总比例、派息、除权除息日、方案进度等
- **用途**: 批量获取某日的分红数据

#### 2. 分红配送详情-东财 (A股)
```python
import akshare as ak
df = ak.stock_fhps_detail_em(symbol="300073")
```
- **说明**: 获取指定个股的历史分红配送详情
- **字段**: 报告期、送转比例、派息、除权除息日等
- **用途**: 获取个股完整分红历史

#### 3. 分红情况-同花顺 (A股) ⭐ 推荐
```python
import akshare as ak
df = ak.stock_fhps_detail_ths(symbol="603444")
```
- **说明**: 获取个股分红情况,**包含税前分红率**
- **字段**: 
  - 分红总额
  - **税前分红率** ✅ (可直接使用)
  - 股利支付率
  - 方案进度
- **优势**: 直接提供分红率,无需计算

#### 4. 分红派息提醒-百度股市通
```python
import akshare as ak
df = ak.news_trade_notify_dividend_baidu(date="20251126")
```
- **说明**: 获取指定日期的分红派息提醒
- **字段**: 除权日、分红金额、送股、转增等
- **用途**: 查询即将分红的股票

---

## 推荐实施方案

### CN 股票 (A股)

**方案1: 使用同花顺接口** ⭐ 推荐
```python
import akshare as ak
df = ak.stock_fhps_detail_ths(symbol="600009")
# 直接获取 '税前分红率' 列
dividend_yield = df['税前分红率'].iloc[0]  # 最新一期
```
- **优点**: 直接提供分红率,无需计算
- **缺点**: 需要验证数据格式(可能是字符串 "1.52%")

**方案2: 从分红记录计算**
```python
import akshare as ak
df = ak.stock_dividend_cninfo(symbol="600009")
# 提取最近一次派息金额,除以当前股价计算
```

### HK 股票 (港股)

**使用财务指标接口**
```python
import akshare as ak
df = ak.stock_hk_financial_indicator_em(symbol="03900")
dividend_ttm = df['每股股息TTM(港元)'].iloc[0]
```

### US 股票 (美股)

**继续使用 yfinance**
```python
import yfinance as yf
ticker = yf.Ticker('AAPL')
dividend_yield = ticker.info['dividendYield']  # 0.4 = 0.4%
```

---

## 数据格式注意事项

### yfinance (美股)
- **格式**: 小数 (0.4 = 0.4%)
- **存储**: 直接存储小数值
- **显示**: `{value:.2f}%`

### AkShare (CN/HK)
- **格式**: 需要验证,可能是:
  - 小数格式 (0.0152 = 1.52%)
  - 字符串格式 ("1.52%")
  - 百分比数值 (1.52 = 1.52%)
- **建议**: 先测试确认格式,再决定存储方式

---

## 下一步行动

1. ✅ **测试同花顺接口**: 验证 `stock_fhps_detail_ths()` 返回的 `税前分红率` 格式
2. ✅ **确定存储格式**: 统一CN/HK/US三个市场的股息率存储格式
3. ✅ **实现获取逻辑**: 在 `fetch_valuation_history.py` 中添加CN/HK股息率获取
4. ✅ **数据验证**: 对比不同来源的股息率数据,确保准确性
