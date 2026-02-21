# 资产管理与导入规范流程 (Asset Management Workflow)

本文档定义了系统中资产导入、符号规范化及 `Canonical ID` 生成的核心规范。为了确保系统的稳定性和数据的一致性，所有操作必须遵循以下流程。

---

## 🔒 核心逻辑固化说明

### 1. 关键文件：`backend/symbol_utils.py`
该文件包含了生成资产唯一标识（Canonical ID）的核心算法。
- **状态**：**已固化 (FROZEN)**
- **规范**：禁止任何人在未经用户明确确认的情况下修改该文件中的导入逻辑。
- **原因**：Canonical ID 是数据库的主键关联基础。一旦生成逻辑发生变动（例如 `^` 符号的处理方式改变），将导致数据库中出现重复资产或数据断裂。

### 2. ID 生成原则 (Canonical ID Rules)
系统采用 `市场:类型:代码` 的三段式结构，并在生成时强制执行以下规范化：
- **符号剔除**：统一剔除代码中的 `^` 符号（例如 `^DJI` 与 `DJI` 都会指向 `US:INDEX:DJI`）。
- **后缀处理**：自动处理 Yahoo 后缀（`.HK`, `.SS`, `.SZ`），ID 中只保留纯代码。
- **补零规则**：
    - 港股 (HK)：强制补齐为 5 位数字（如 `700` -> `00700`）。
    - A 股 (CN)：强制补齐为 6 位数字（如 `1` -> `000001`）。
- **去歧义**：上证综合指数强制映射为 `CN:INDEX:000001`，与平安银行个股完全隔离。

---

## 📂 资产扩容操作指南

如果你需要增加、删除或修改系统中的资产，请遵循以下步骤，**无需修改 `symbol_utils.py` 代码**。

### 第一步：编辑清单
1. 打开 `imports/symbols.txt`。
2. 将新的代码添加到对应的分类标题下方（例如 `# === 美股 (US Stocks) ===`）。
3. **注意格式**：美股指数建议使用不带 `^` 的形式（如 `DJI`）。

### 第二步：同步数据库
运行以下命令，将文本清单同步到数据库的 `Watchlist` 表中：
```bash
python3 reset_and_redownload_all.py
```
> [!TIP]
> **交互建议**：运行后询问是否清理旧数据时，通常选择 **`n`**。

### 第三步：数据获取与加工 (一键流水线)
你可以拷贝并运行以下组合命令，它将按顺序完成抓取、清洗及导出。导出文件将存放在 **`outputs/`** 目录下。

```bash
python3 fetch_financials.py && \
python3 download_full_history.py && \
python3 fetch_valuation_history.py && \
python3 run_etl.py && \
python3 export_daily_csv.py && \
python3 export_financials_formatted.py
```
---
 
## 📊 数据导出规范 (Data Export Specification)

所有导出脚本（如 `export_financials_formatted.py`）必须遵循以下数据格式规范：

### 1. 强制使用典范代码 (Mandatory Canonical ID)
- **要求**：CSV 文件的 `symbol` 列必须填充**典范代码**（例如 `HK:STOCK:09988`），禁止填充纯代码（如 `09988`）。
- **目的**：确保导出的数据在导入其他分析工具或系统时，能够通过唯一标识符准确关联。

### 2. 数值格式化
- **单位统一**：财报相关金额数值应转换为“**亿**”单位（100 Million），并在列名中注明（如 `revenue (亿)`）。
- **编码标准**：导出文件应使用 `utf-8-sig` 编码，以确保在 Excel 中中文不乱码。

---

## 📂 输出结果说明
运行完成后，你可以在系统的 **`outputs/`** 文件夹下查看结果：
- **`market_data_daily_full.csv`**: 全量日线行情、涨跌幅及历史估值 (PE/PB)。
- **`financials_overview_v2.csv`**: 关键财报指标（数据已格式化，单位为“亿”）。
- **`financial_history.csv`**: 原始维度的财报历史数据。

---

## ⚠️ 修改权限声明

如果开发人员（或 AI 助理）认为必须修改 `backend/symbol_utils.py` 中的导入逻辑：
1. **必须首先向用户提交书面说明**，解释修改的必要性及潜在风险。
2. **必须展示修改前后的 ID 变化示例**。
3. **只有在获得用户明确的“确认修改”指令后，方可动动代码。**

---
*文档版本: 1.0.0*
*更新日期: 2026-01-08*
