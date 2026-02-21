# 数据获取代码重构 - 修改清单

## 文件: download_full_history.py

### 修改位置 1: convert_to_yfinance_symbol() 函数 (第18-66行)

**当前问题**: 硬编码的symbol格式转换逻辑

**修改方案**:
```python
def convert_to_yfinance_symbol(symbol: str, market: str) -> str:
    """
    转换为yfinance格式
    优先使用配置表映射(指数),然后使用通用转换函数(个股/ETF)
    """
    from backend.symbol_utils import get_yahoo_symbol
    
    s = symbol.strip().upper()
    
    # 1. 优先检查指数配置表
    yf_symbol = get_yfinance_symbol(s, market)
    if yf_symbol != s:
        return yf_symbol
    
    # 2. 对于个股/ETF,使用 symbol_utils 的通用转换函数
    yf_symbol = get_yahoo_symbol(s, market)
    
    return yf_symbol
```

**改进点**:
- 移除了34-66行的硬编码逻辑
- 使用 `symbol_utils.get_yahoo_symbol()` 统一处理
- 代码从49行减少到18行

---

## 文件: backfill_valuation_history.py

### 当前状态
- 只通过财报计算PE
- 未使用AkShare的估值接口

### 需要添加的功能

#### 1. A股历史PE/PB数据获取
```python
def fetch_cn_valuation_history(symbol: str) -> pd.DataFrame:
    """
    获取A股历史估值数据
    使用 AkShare stock_value_em() 接口
    """
    import akshare as ak
    
    try:
        # 从 Canonical ID 提取纯代码
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        # 调用 AkShare 接口
        df = ak.stock_value_em(symbol=code)
        
        # 返回字段: 数据日期, PE(TTM), PE(静), 市净率, 市销率, 市现率
        return df
        
    except Exception as e:
        logger.error(f"获取A股估值数据失败 {symbol}: {e}")
        return None
```

#### 2. 港股历史PE/PB数据获取
```python
def fetch_hk_valuation_history(symbol: str, indicator: str = "市盈率") -> pd.DataFrame:
    """
    获取港股历史估值数据
    使用 AkShare stock_hk_indicator_eniu() 接口
    """
    import akshare as ak
    
    try:
        # 从 Canonical ID 提取纯代码
        code = symbol.split(':')[-1] if ':' in symbol else symbol
        
        # 转换为 hk + 5位代码格式
        hk_code = f"hk{code}"
        
        # 调用 AkShare 接口
        df = ak.stock_hk_indicator_eniu(symbol=hk_code, indicator=indicator)
        
        # 返回字段: date, pe/pb, price
        return df
        
    except Exception as e:
        logger.error(f"获取港股估值数据失败 {symbol}: {e}")
        return None
```

#### 3. 集成到主流程
```python
def backfill_valuation_data():
    """回填估值数据 - 优先使用AkShare接口"""
    
    with Session(engine) as session:
        # 获取所有资产
        watchlist = session.exec(select(Watchlist)).all()
        
        for item in watchlist:
            market = item.market
            symbol = item.symbol
            
            if market == 'CN':
                # A股: 使用 stock_value_em
                df = fetch_cn_valuation_history(symbol)
                if df is not None:
                    save_cn_valuation_to_db(symbol, df, session)
                    
            elif market == 'HK':
                # 港股: 使用 stock_hk_indicator_eniu
                df_pe = fetch_hk_valuation_history(symbol, "市盈率")
                df_pb = fetch_hk_valuation_history(symbol, "市净率")
                if df_pe is not None or df_pb is not None:
                    save_hk_valuation_to_db(symbol, df_pe, df_pb, session)
                    
            elif market == 'US':
                # 美股: 继续使用现有的计算方法
                # (因为没有历史PE数据源)
                pass
```

---

## 实施优先级

### 高优先级 ✅
1. 修改 `download_full_history.py` 的symbol转换函数
2. 为A股添加历史PE/PB数据获取

### 中优先级
3. 为港股添加历史PE/PB数据获取

### 低优先级
4. 美股PE数据(暂无免费历史数据源)

---

## 注意事项

1. **保持ETL流程**: 不修改ETL相关代码
2. **向后兼容**: 现有数据不受影响
3. **错误处理**: 添加完善的异常处理
4. **测试验证**: 每个修改后都要测试

---

**创建时间**: 2026-01-08
**状态**: 待实施
