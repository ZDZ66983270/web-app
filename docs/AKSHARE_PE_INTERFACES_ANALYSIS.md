# AkShare 日线市盈率接口完整分析

## 📋 分析日期
2026-01-08

## 🎯 分析目标
在 AkShare 文档中查找所有可能包含**日线市盈率(PE)**数据的接口

---

## ✅ 发现的接口列表

### 1. ⭐⭐⭐⭐ **个股估值** (推荐)

**接口名称**: `stock_value_em`  
**数据源**: 东方财富网-数据中心-估值分析  
**目标地址**: https://data.eastmoney.com/gzfx/detail/300766.html

**功能**: 获取个股的**历史每日估值数据**,包含PE、PB、PS等指标

**输入参数**:
- `symbol`: 股票代码 (如 "300766")

**输出字段**:
```
数据日期, 当日收盘价, 当日涨跌幅, 市盈率动态, 市盈率静态, 市盈率TTM, 
市净率, 市销率, 市现率, PEG值
```

**示例代码**:
```python
import akshare as ak
df = ak.stock_value_em(symbol="300766")
print(df)
```

**数据示例**:
```
    数据日期  当日收盘价  当日涨跌幅  市盈率动态  市盈率静态  市盈率TTM  市净率  市销率
0  2019-03-25   18.84   44.04      ...      ...      ...   ...   13.98
1  2019-03-26   20.72    9.98      ...      ...      ...   ...   15.37
...
```

**✅ 优点**:
- 包含**历史每日PE数据** ⭐⭐⭐⭐
- 提供多种PE类型(动态、静态、TTM)
- 数据完整,覆盖上市以来所有交易日
- 同时包含PB、PS等其他估值指标

**❌ 限制**:
- 仅支持A股
- 需要逐个股票查询

---

### 2. ⭐⭐⭐ **港股个股指标** (部分可用)

**接口名称**: `stock_hk_indicator_eniu`  
**数据源**: 亿牛网  
**目标地址**: https://eniu.com/gu/hk01093/roe

**功能**: 获取港股个股的历史指标数据

**输入参数**:
- `symbol`: 港股代码 (如 "hk01093")
- `indicator`: 指标类型,可选 `['市盈率', '市净率', '股息率', 'ROE', '市值']`

**示例代码**:
```python
import akshare as ak
df = ak.stock_hk_indicator_eniu(symbol="hk01093", indicator="市盈率")
print(df)
```

**⚠️ 注意**: 文档标注"该数据源暂未更新数据",需要测试验证是否可用

---

### 3. ⭐⭐⭐ **港股估值指标**

**接口名称**: `stock_hk_valuation_baidu`  
**数据源**: 百度股市通  
**目标地址**: https://gushitong.baidu.com/stock/hk-06969

**功能**: 获取港股的历史估值数据

**输入参数**:
- `symbol`: 港股代码 (如 "06969")
- `indicator`: 指标类型,可选 `['总市值', '市盈率', '市净率', '市销率', '市现率', '股息率']`
- `period`: 时间周期,可选 `['近一年', '近三年', '近五年', '全部']`

**示例代码**:
```python
import akshare as ak
df = ak.stock_hk_valuation_baidu(symbol="06969", indicator="市盈率", period="近一年")
print(df)
```

**数据示例**:
```
        date   value
0  2023-11-21  25.30
1  2023-11-22  25.45
...
```

**✅ 优点**:
- 支持港股历史PE数据
- 可选择不同时间周期

---

### 4. ⭐⭐ **A股等权重与中位数市盈率**

**接口名称**: `stock_a_ttm_lyr`  
**数据源**: 乐咕乐股  
**目标地址**: https://www.legulegu.com/stockdata/a-ttm-lyr

**功能**: 获取**A股市场整体**的等权重市盈率与中位数市盈率

**示例代码**:
```python
import akshare as ak
df = ak.stock_a_ttm_lyr()
print(df)
```

**数据示例**:
```
        date  middlePETTM  ...  close
0  2005-01-05       28.79  ...   0.00
1  2005-01-06       29.18  ...   0.00
...
```

**✅ 优点**:
- 提供市场整体PE趋势
- 历史数据完整(从2005年开始)

**❌ 限制**:
- 仅市场整体数据,非个股

---

### 5. ⭐⭐ **主板市盈率**

**接口名称**: `stock_market_pe_lg`  
**数据源**: 乐咕乐股  
**目标地址**: https://legulegu.com/stockdata/shanghaiPE

**功能**: 获取主板(上证/深证/创业板/科创板)的市盈率

**输入参数**:
- `symbol`: 市场类型,可选 `['上证', '深证', '创业板', '科创版']`

**示例代码**:
```python
import akshare as ak
df = ak.stock_market_pe_lg(symbol="上证")
print(df)
```

**数据示例**:
```
        日期      指数  平均市盈率
0  1999-01-29  1134.67    34.03
1  1999-02-09  1090.08    33.50
...
```

**✅ 优点**:
- 提供市场/板块整体PE
- 历史数据完整

**❌ 限制**:
- 仅市场/板块数据,非个股

---

### 6. ⭐ **指数市盈率**

**接口名称**: `stock_index_pe_lg`  
**数据源**: 乐咕乐股

**功能**: 获取指数的市盈率数据

**❌ 限制**: 仅指数,非个股

---

## 📊 完整对比表

| 接口名称 | 适用市场 | 数据类型 | 历史PE | 推荐度 | 备注 |
|---------|---------|---------|--------|--------|------|
| `stock_value_em` | A股 | 个股 | ✅ 每日 | ⭐⭐⭐⭐ | **最佳选择** |
| `stock_hk_indicator_eniu` | 港股 | 个股 | ✅ 每日 | ⭐⭐⭐ | 数据源可能未更新 |
| `stock_hk_valuation_baidu` | 港股 | 个股 | ✅ 每日 | ⭐⭐⭐ | 百度股市通 |
| `stock_a_ttm_lyr` | A股 | 市场整体 | ✅ 每日 | ⭐⭐ | 市场整体,非个股 |
| `stock_market_pe_lg` | A股 | 板块/市场 | ✅ 月度 | ⭐⭐ | 月度数据,非日线 |
| `stock_us_hist` | 美股 | 个股 | ❌ 无 | - | 仅OHLCV |
| `stock_zh_a_hist` | A股 | 个股 | ❌ 无 | - | 仅OHLCV |
| `stock_hk_hist` | 港股 | 个股 | ❌ 无 | - | 仅OHLCV |

---

## 🎯 结论与建议

### ✅ **发现重大突破!**

**`stock_value_em` 接口提供A股个股的历史每日PE数据!**

这是之前测试中**遗漏**的接口,它提供:
- ✅ 历史每日PE数据
- ✅ 多种PE类型(动态、静态、TTM)
- ✅ 完整的历史覆盖
- ✅ 同时包含PB、PS等指标

### 📝 更新后的数据源方案

#### **A股** ⭐⭐⭐⭐
**推荐**: `stock_value_em`
```python
import akshare as ak
df = ak.stock_value_em(symbol="600519")  # 贵州茅台
# 返回: 数据日期, 当日收盘价, 市盈率动态, 市盈率静态, 市盈率TTM, 市净率, 市销率...
```

#### **港股** ⭐⭐⭐
**推荐**: `stock_hk_valuation_baidu`
```python
import akshare as ak
df = ak.stock_hk_valuation_baidu(symbol="00700", indicator="市盈率", period="全部")
```

**备选**: `stock_hk_indicator_eniu` (需测试)

#### **美股** ⭐⭐
**方案**: 
- 自行计算 (Price / EPS)
- 使用 Futu API (如果支持美股)

---

## 🔧 下一步行动

1. **立即测试** `stock_value_em` 接口
2. **验证数据质量**:
   - PE数据完整性
   - 历史覆盖范围
   - 数据更新频率
3. **测试** `stock_hk_valuation_baidu` 港股接口
4. **更新** PE数据源对比文档
5. **集成**到VERA系统

---

## 📌 重要发现总结

1. ✅ **A股有历史每日PE**: `stock_value_em`
2. ✅ **港股有历史每日PE**: `stock_hk_valuation_baidu`
3. ❌ **美股无历史每日PE**: 需自行计算或使用其他数据源
4. ⭐ **Futu API 仍是港股最佳选择** (100%数据完整性)

---

**最后更新**: 2026-01-08  
**文档来源**: https://akshare.akfamily.xyz/data/stock/stock.html#id9
