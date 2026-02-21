# 哼哼哈嘿（hengha）

> 投资标的价值评估AI助手 | GitHub代号: Project 20251211

这是一个基于 Vite + React 的智能投资分析应用,帮助用户对自选的投资标的进行全面的价值评估。

## ✨ 应用特色

本应用的核心价值在于:

### 一、价值评估为主,风险识别为辅

- **价值分析**: 评估投资标的的内在价值和当前估值水平
- **机会洞察**: 识别潜在的投资机会和有利因素
- **风险识别**: 客观列出需要关注的风险点,而非简单的"高风险"标签
- **综合评分**: 多维度评估,给出客观的综合评分

**核心理念**: 不推荐投资标的,只评估用户已选择的标的

### 二、灵活的数据获取与补充机制

- **免费行情数据**: 通过 iFinance 或其他平台获取免费行情数据(有延时)
- **用户贡献数据**: 允许用户通过上传截图来作为数据的补充,从而丰富数据库
- **数据互补**: 结合自动获取和用户上传,构建更完整的数据体系

### 三、投资大师理论模型化

- **理论模型化**: 将投资大师的经典理论转化为可量化的评估模型
- **价值评估体系**: 为用户提供多维度的价值分析框架
- **客观中立**: 不做投资推荐,只提供客观评估
- **多维度分析**: 
  - **股票评估**: 价值分析、周期判断、技术面分析、基本面分析
  - **基金评估**: 价值评估、费用效率、持仓分析、跟踪误差、资金流向

**免责声明**: 本应用仅提供数据分析和价值评估,不构成投资建议。投资决策由用户自主做出,风险自负。

---


## 🚀 快速开始

### 1. 前置准备
请确保您的电脑安装了 **Node.js** (推荐 v18+)。

### 2. 安装依赖
在终端终端进入 `web-app` 目录并运行：
```bash
cd "My Docs/Privates/22-AI编程/AI+风控App/web-app"
npm install
```

### 3. 本地运行 (Mac)
```bash
npm run dev
```
启动后终端会显示访问地址，通常为 `http://localhost:5173`。

---

## 📱 手机调试与访问

为了方便您在手机上直接查看效果，无论是 iOS 还是 Android，只需确保**手机和电脑连接同一个 WiFi**。

1. **启动服务**
   我们已为您配置好了网络共享模式，只需运行：
   ```bash
   npm run dev
   ```

2. **获取访问地址**
   查看终端输出的 `Network` 地址，例如：
   ```
     ➜  Local:   http://localhost:5173/
     ➜  Network: http://192.168.1.5:5173/  <-- 使用这个地址
   ```

3. **手机访问**
   在手机浏览器（Safari/Chrome）中输入上面的 `Network` 地址（如 `192.168.1.5:5173`），即可直接使用。

---

## 📦 如何打包为 App

如果您希望将此项目发布为真正的手机 App (iOS/Android)，推荐以下两种方案：

### 方案 A：Web App 直出 (最快)
本项目本质是一个响应式网页，您可以直接在手机浏览器点击 **"分享" -> "添加到主屏幕"**。
我们已配置了 PWA 基础结构，添加后它会像原生 App 一样全屏运行，没有浏览器地址栏。

### 方案 B：使用 Capacitor 打包 (原生体验)
如果您需要发布到 App Store，可以使用 Capacitor 将此网页“包裹”成原生 App。

**步骤简述：**
1. 安装 Capacitor: `npm install @capacitor/core @capacitor/cli`
2. 初始化: `npx cap init`
3. 构建网页: `npm run build`
4. 添加平台: `npm install @capacitor/ios @capacitor/android`
5. 生成项目: `npx cap add ios`
6. 打开 Xcode 编译: `npx cap open ios`

---

## 🛠 文件结构
- `src/components`: UI 组件 (Header, SearchBar, AnalysisResult...)
- `src/utils`: 工具函数 (包括 Mock 数据)
- `src/index.css`: 全局样式与变量定义
- `backend/`: 后端API服务 (FastAPI + SQLModel)

---

## 📚 开发文档

- **产品定位**: [PRODUCT_POSITIONING.md](./PRODUCT_POSITIONING.md) - 应用定位、评估体系和表达规范
- **业务流程与页面布局**: [UX_DESIGN.md](./UX_DESIGN.md) - 用户旅程、页面结构和交互设计
- **系统架构设计**: [ARCHITECTURE.md](./ARCHITECTURE.md) - 完整的系统架构、部署方案和发布路线图
- **后台开发路线图**: [BACKEND_ROADMAP.md](./BACKEND_ROADMAP.md) - 详细的后台开发计划和实施步骤
- **后台开发计划**: [backend/DEVELOPMENT_PLAN.md](./backend/DEVELOPMENT_PLAN.md) - 后台开发任务清单

## 💡 UI/UX 规范 (CRITICAL)
- **列表显示**: 必须优先显示股票/基金的**中文名称** (或通用名称)，而非代码。
  - 正确: "苹果", "贵州茅台"
  - 错误: "AAPL", "600519"
- **搜索添加**: 添加后应立即获取并保存名称，确保列表展示友好。

---

## 🛡️ Core Data Strategy (三合一数据策略)

本系统采用独特的多源数据融合策略，确保在不同市场状态下（开盘/闭市/节假日）都能获得最完整的数据展示。

### 1. 统一字段映射 (Unified Field Mapping)
解决多数据源（AkShare/Yahoo）返回字段名不一致的问题（如 `volume` vs `Volume` vs `成交量`）。所有上游数据在进入系统前，均被强制映射为内部标准：
- `open`, `high`, `low`, `close` (基础四价)
- `volume` (成交量)
- `turnover` (成交额，自动推算)
- `pct_change` (涨跌幅，自动计算)

### 2. 智能指标补全 (Indicator Enrichment)
当主数据源（AkShare）缺失关键财务指标时，系统会自动触发 **Yahoo Finance** 备用接口进行补全，确保以下核心指标始终可用：
- `pe` (市盈率)
- `dividend_yield` (股息率)
- `eps` (每股收益)
- `market_cap` (总市值)

### 3. 灾备计算逻辑 (Fallback Calculation)
针对闭市或历史数据缺失涨跌幅的情况，系统内置自动演算引擎：
- **涨跌幅** = `(今日收盘 - 昨日收盘) / 昨日收盘 * 100%`
- **成交额** = `今日收盘 * 今日成交量` (若源数据缺失)
- **归零保护**：当实时价格为 0 时，自动回溯最近一个有效交易日的收盘价。

### 4. 数据刷新机制 (Data Refresh Mechanism)
为了平衡数据实时性与服务器资源，前端“刷新”按钮采用了双重交互逻辑：
- **双击 (Double Tap)**：触发 **Force Refresh**（2秒内连续点击）。无视所有缓存和规则，强制重新抓取全市场所有关注标的的数据。**适用于修复数据显示异常或强制同步最新行情。**

### 5. 美股历史数据策略 (US Daily History Strategy)

针对美股历史数据（K线/趋势分析），由于全量数据过于庞大（1.6万只股票 x 几十年），我们采取 **"关键标的按需存储" (Selective Persistence)** 策略。

#### 接口技术规格
- **接口名称**: `stock_us_daily` (源自新浪财经 Sina Finance)
- **技术特点**: 
  - 支持 **前复权 (QFQ)** 数据，确保长期收益率计算准确（包含分红/拆股调整）。
  - 响应速度快，稳定性高（相比全量接口）。
- **适用场景**: 仅对用户 **自选列表 (Watchlist)** 中的美股进行增量更新。

#### 字段映射标准 (Field Mapping)
我们建立如下严格的字段对应关系，确保数据库的一致性：

| 字段 (Key) | 类型 (Type) | 含义 (Description) | 备注 (Notes) |
| :--- | :--- | :--- | :--- |
| **date** | `datetime` | **日期** | 格式 `YYYY-MM-DD` |
| **open** | `float` | **开盘价** | 复权后的开盘价格 |
| **high** | `float` | **最高价** | 当日最高价 |
| **low** | `float` | **最低价** | 当日最低价 |
| **close** | `float` | **收盘价** | **核心数据** (用于计算涨幅/均线) |
| **volume** | `float` | **成交量** | 注意单位，通常为股数 |

*(注：系统默认请求 `adjust="qfq"` 获取复权数据，以反映真实的投资回报率。)*

### 6. A股历史数据策略 (CN Daily History Strategy)

A股历史数据同样采用 **按需抓取** 策略。

#### 接口技术规格
- **接口名称**: `stock_zh_a_daily` (源自新浪财经)
- **参数说明**: `adjust="qfq"` (前复权)
- **适用范围**: 沪深京 A 股

#### 字段映射标准 (Field Mapping)

| 字段 (Key) | 类型 (Type) | 含义 (Description) | 备注 (Notes) |
| :--- | :--- | :--- | :--- |
| **date** | `object/str` | **交易日** | 格式 `YYYY-MM-DD` |
| **open** | `float` | **开盘价** | 前复权 |
| **high** | `float` | **最高价** | 前复权 |
| **low** | `float` | **最低价** | 前复权 |
| **close** | `float` | **收盘价** | 前复权 |
| **volume** | `float` | **成交量** | 单位：**股** (Share) |
| **amount** | `float` | **成交额** | 单位：**元** (CNY) |
| **outstanding_share** | `float` | **流通股本** | 单位：**股** |
| **turnover** | `float` | **换手率** | 小数格式 (0.01 = 1%) |

### 7. 港股历史数据策略 (HK Daily History Strategy)

港股历史数据同样采用 **按需抓取** 策略。

#### 接口技术规格
- **接口名称**: `stock_hk_daily` (源自新浪财经)
- **参数说明**: `adjust="qfq"` (前复权)
- **适用范围**: 港股所有上市公司

#### 字段映射标准 (Field Mapping)

| 字段 (Key) | 类型 (Type) | 含义 (Description) | 备注 (Notes) |
| :--- | :--- | :--- | :--- |
| **date** | `object/str` | **交易日** | 格式 `YYYY-MM-DD` |
| **open** | `float` | **开盘价** | 前复权 |
| **high** | `float` | **最高价** | 前复权 |
| **low** | `float` | **最低价** | 前复权 |
| **close** | `float` | **收盘价** | **核心数据** |
| **volume** | `float` | **成交量** | 单位：**股** |

*(注：港股接口通常只返回核心6个字段，不包含成交额和换手率。)*

### 8. 全市场历史数据统一映射表 (Unified History Field Mapping)

为确保数据清洗的一致性，系统内部采用以下标准字段名。各市场原始接口返回的字段 (Key) 将被统一映射如下：

| **标准化字段 (Core Key)** | **CN (A股)**<br>`stock_zh_a_daily` | **HK (港股)**<br>`stock_hk_daily` | **US (美股)**<br>`stock_us_daily` | **数据类型** | **说明** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **date** | `date` | `date` | `date` | `string` | YYYY-MM-DD |
| **open** | `open` | `open` | `open` | `float` | QFQ 开盘价 |
| **high** | `high` | `high` | `high` | `float` | QFQ 最高价 |
| **low** | `low` | `low` | `low` | `float` | QFQ 最低价 |
| **close** | `close` | `close` | `close` | `float` | **QFQ 收盘价** |
| **volume** | `volume` | `volume` | `volume` | `float` | 成交量 (股) |
| **amount** | `amount` | N/A | N/A | `float` | 成交额 (元) |
| **outstanding_share** | `outstanding_share`| N/A | N/A | `float` | 流通股本 |
| **turnover** | `turnover` | N/A | N/A | `float` | 换手率 (小数) |

*(注：N/A 表示该接口不直接返回该字段，系统后续可根据收盘价x成交量进行估算，或留空)*

---

## 🤝 贡献指南

欢迎贡献代码!请参考以下文档:
- 前端开发: 遵循React最佳实践
- 后端开发: 参考 `BACKEND_ROADMAP.md`
- 提交PR前请确保代码通过测试

---

## 📦 版本控制

本项目使用Git进行版本控制,代码托管在GitHub。

### 快速开始

```bash
# 查看状态
git status

# 提交更改
git add .
git commit -m "feat: 添加新功能"
git push
```

详细的GitHub使用指南请查看: [GITHUB_GUIDE.md](./GITHUB_GUIDE.md)

## 🏗️ 系统重构设计文档

为支持后续系统升级与维护，我们整理了详细的**系统设计与重构指南**，涵盖：
- 系统架构图 (Legacy vs New)
- 数据库Schema分析
- 3阶段重构路线图
- 关键模块说明

📄 **阅读文档**: [design_for_refactoring.md](./design_for_refactoring.md)
