# 📊 财务分析 AI Agent

一个真正的 **AI Agent** 财务分析工具 —— 你可以**用中文直接对话**让 AI 分析任何上市公司,也可以一键生成图文并茂的专业研报,支持四种格式下载。

> 🌐 **在线体验**:[https://alexnanl-finance-agent-app-vjvsgh.streamlit.app/](https://alexnanl-finance-agent-app-vjvsgh.streamlit.app/)

---

## ✨ 核心功能

### 🤖 AI 对话模式(默认)
通过自然语言对话,AI 自主调用工具完成各种分析:

```
你: 苹果 2024 年怎么样
AI: [调用 compute_ratios] 展示 ROE/ROA/净利率/毛利率 + 文字解读

你: 帮我做杜邦分析
AI: [调用 dupont_analysis] 展示杜邦瀑布图 + 三因素拆解

你: 跟微软比一下
AI: [调用 peer_comparison] 展示对比柱状图 + 优劣判断

你: 给我特斯拉的完整报告
AI: [调用 generate_full_report] 提供下载按钮
```

AI 会**记住上下文** — 你说"看看趋势"它知道继续看苹果的趋势,不需要重复公司名。

### 📊 经典分析模式
传统的"输入公司 → 一键生成"模式,适合需要全面分析时:

- **比率分析** — 盈利、运营、偿债、现金流(15+ 指标)
- **杜邦分析** — ROE 三因素分解 + 历年趋势
- **趋势分析** — 多年度交互式图表
- **同行业比较** — 按行业 + 规模自动匹配同行
- **基准分析** — 优秀/良好/一般/偏弱评级

### 📄 智能报告(v6 新)
报告 Tab 采用**"先呈现数据 → AI 基于数据深度分析"**的专业研报结构:

- **8 个章节**:公司概览、盈利能力、运营效率、偿债能力、杜邦分析、历年趋势、同行对标、综合诊断
- **每章节都是数据先行**:相关图表 / 数据表先呈现,然后 AI 基于这些数据展开 250-400 字的专业分析
- **AI 主动引用图表**:文字会说"上图显示毛利率从 38% 提升到 46%..."
- **4 种格式下载**:📄 Markdown / 🌐 HTML / 📝 Word / 📑 PDF

---

## 🚀 快速开始

### 方式一:直接使用在线版
访问 [https://alexnanl-finance-agent-app-vjvsgh.streamlit.app/](https://alexnanl-finance-agent-app-vjvsgh.streamlit.app/) 即可,无需安装。

### 方式二:本地部署

```bash
# 1. 克隆仓库
git clone https://github.com/alexnanl/finance-agent.git
cd finance-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 OpenAI API Key(AI 功能需要)
# 创建 .streamlit/secrets.toml 文件,内容:
# OPENAI_API_KEY = "sk-proj-xxxxx"

# 4. 启动
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

> ⚠️ **注意**:本地部署如需 PDF 导出和报告图表嵌入,Linux/Mac 还需安装系统包(见 `packages.txt`)。

---

## 📋 输入格式

支持公司名(中英文)和股票代码两种输入方式:

| 类型 | 示例 |
|------|------|
| 中文公司名 | `苹果`、`腾讯`、`贵州茅台`、`丰田` |
| 英文公司名 | `Apple`、`Tencent`、`Toyota`、`Microsoft` |
| 美股代码 | `AAPL`、`TSLA`、`MSFT` |
| 港股代码 | `0700.HK`(腾讯)、`9988.HK`(阿里)、`1810.HK`(小米) |
| A 股(上交所) | `600519.SS`(贵州茅台)、`601318.SS`(中国平安) |
| A 股(深交所) | `000858.SZ`(五粮液)、`300750.SZ`(宁德时代) |
| 日股 | `7203.T`(丰田)、`6758.T`(索尼) |
| 英股 | `HSBA.L`(汇丰) |
| 德股 | `SAP.DE`(SAP) |

不知道代码也没关系,系统会自动通过 Yahoo Finance 搜索匹配。

---

## 📁 项目结构

```
finance-agent/
├── app.py                       # Streamlit 主入口(模式切换 + 经典分析)
├── requirements.txt             # Python 依赖
├── packages.txt                 # 系统依赖(Streamlit Cloud 用)
├── README.md
└── utils/
    ├── __init__.py
    ├── data_fetcher.py          # yfinance 数据抓取 + 公司名搜索
    ├── ratios.py                # 比率计算 + 杜邦分析
    ├── benchmark.py             # 基准评级 + 同行对比
    ├── charts.py                # Plotly 交互式图表
    ├── report.py                # 规则模板报告(兜底)
    ├── report_builder.py        # AI 增强报告 + 多格式导出 ⭐
    ├── i18n.py                  # 中英文界面切换
    ├── tools.py                 # AI Agent 可调用的工具集 ⭐
    ├── ai_agent.py              # OpenAI Function Calling 主循环 ⭐
    └── chat_page.py             # AI 对话页面 ⭐
```

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | Streamlit |
| 数据源 | yfinance(Yahoo Finance) |
| 图表 | Plotly(交互式)+ Kaleido(图片导出) |
| LLM | OpenAI GPT-4o-mini(Function Calling) |
| 报告导出 | python-docx(Word)、weasyprint(PDF) |
| 国际化 | 自研 i18n 模块(中英文) |

---

## 💡 设计亮点

### 1. 真正的 AI Agent 架构
不是"AI 增强工具",而是符合 Agent 三大特征:
- **LLM 主导决策** — 用户用自然语言描述,AI 自己决定调用什么工具
- **多步推理** — 单轮对话内可调用多个工具,AI 会基于中间结果调整
- **状态记忆** — 跨对话轮记住上下文(已分析的公司、对比的同行等)

### 2. 智能同行匹配
不再是写死的"科技行业 = 苹果微软谷歌",而是按 **行业 + 市值规模** 双重匹配。分析 Snowflake(700 亿市值)推荐的是 Datadog/Palantir,而不是 3 万亿的苹果。

### 3. 报告"数据→分析"模式
告别"图表一堆 / 文字一坨"的传统报告,每章节先呈现具体图表/表格,再由 AI 基于这些数据展开专业分析,符合金融研报的标准写法。

### 4. 反 Token 浪费设计
- LLM 报告生成有缓存(同公司+年份不重复调)
- 提供"重新生成"按钮供用户主动触发
- AI 对话单 session 限 60 条消息,单条限 1000 字

---

## 🔧 扩展方向

- **国内数据源接入** — 用 `akshare` 替换部分逻辑,改善 A 股数据完整度(yfinance 仅 4 年年报)
- **行业特化基准** — 银行业、科技业、零售业用不同的"优秀/良好"阈值
- **多 LLM 支持** — 让用户在 OpenAI / Gemini / DeepSeek / 国内模型间切换
- **趋势预测** — 用 ARIMA / Prophet 给指标做未来 1-2 年预测
- **PDF 字体优化** — 解决 weasyprint 中文字体问题(目前推荐 HTML 转 PDF)

---

## ⚠️ 局限性

1. **yfinance 数据限制** — 通常仅提供近 4 年年报,部分小盘股字段缺失
2. **OpenAI API 必需** — AI 对话和增强报告功能需要 API Key,免费用户只能用规则模板
3. **国内访问** — Streamlit Cloud 部署在海外,中国大陆访问可能不稳定
4. **不构成投资建议** — 本工具仅供学习参考

---

## 📝 License

MIT

---

## 🤝 反馈与贡献

欢迎在 GitHub Issues 提反馈或 PR。如果这个项目对你有帮助,给个 ⭐ 支持下吧!
