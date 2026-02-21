# 📚 项目文档目录

本目录集中存放所有项目相关的技术文档和指南。

## 📋 文档分类

### 🔧 数据获取与API规范
- **[DATA_ACQUISITION_GUIDE.md](./DATA_ACQUISITION_GUIDE.md)** - 数据获取途径完整梳理
  - 日线行情数据 (OHLCV)
  - 市盈率 (PE) 数据
  - 市净率 (PB) 数据
  - 财报数据
  - 接口参数规范详解
  - ETF和指数参数规范

- **[SYMBOL_FORMAT_MAPPING.md](./SYMBOL_FORMAT_MAPPING.md)** - Symbol格式映射关系总结
  - 个股Symbol映射
  - ETF Symbol映射
  - 指数Symbol映射
  - asset_type识别规则

- **[AKSHARE_PE_INTERFACES_ANALYSIS.md](./AKSHARE_PE_INTERFACES_ANALYSIS.md)** - AkShare PE接口分析
  - AkShare日线市盈率接口完整分析
  - 发现的可用接口列表

- **[PE_DATA_SOURCES_COMPARISON.md](./PE_DATA_SOURCES_COMPARISON.md)** - PE数据源对比
  - yfinance vs AkShare vs Futu API
  - 各数据源PE数据可用性对比

- **[DATA_SOURCE_PRIORITY.md](./DATA_SOURCE_PRIORITY.md)** - 数据源优先级策略

### 🏗️ 架构与设计
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - 系统架构文档
- **[design_for_refactoring.md](./design_for_refactoring.md)** - 重构设计文档

### 📊 数据库与后端
- **[INDEX_TABLE_SUMMARY.md](./INDEX_TABLE_SUMMARY.md)** - 指数表设计总结
- **[BACKEND_ROADMAP.md](./BACKEND_ROADMAP.md)** - 后端开发路线图

### 📖 使用指南
- **[STOCK_ADDITION_GUIDE.md](./STOCK_ADDITION_GUIDE.md)** - 股票添加指南
- **[BATCH_USAGE.md](./BATCH_USAGE.md)** - 批处理使用指南
- **[GITHUB_GUIDE.md](./GITHUB_GUIDE.md)** - GitHub使用指南

### 🎨 产品与设计
- **[PRODUCT_POSITIONING.md](./PRODUCT_POSITIONING.md)** - 产品定位
- **[UX_DESIGN.md](./UX_DESIGN.md)** - UX设计文档

## 🔍 快速查找

### 我想了解...

**如何获取股票数据?**
→ 查看 [DATA_ACQUISITION_GUIDE.md](./DATA_ACQUISITION_GUIDE.md)

**Symbol格式转换规则?**
→ 查看 [SYMBOL_FORMAT_MAPPING.md](./SYMBOL_FORMAT_MAPPING.md)

**如何添加新股票?**
→ 查看 [STOCK_ADDITION_GUIDE.md](./STOCK_ADDITION_GUIDE.md)

**PE数据从哪里获取?**
→ 查看 [PE_DATA_SOURCES_COMPARISON.md](./PE_DATA_SOURCES_COMPARISON.md)

**系统架构是什么?**
→ 查看 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 📝 文档维护

### 更新规则
1. 所有技术文档统一放在 `docs/` 目录
2. 文档命名使用大写字母和下划线 (如 `DATA_ACQUISITION_GUIDE.md`)
3. 每个文档开头注明最后更新日期和版本号
4. 重要变更需要在文档中标注

### 文档版本
- 使用语义化版本号 (如 v1.0, v2.1)
- 重大更新增加主版本号
- 小修改增加次版本号

---

**最后更新**: 2026-01-08  
**维护者**: AI Assistant
