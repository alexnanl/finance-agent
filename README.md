# 📊 财务分析 AI Agent

一个基于 Streamlit 的财务分析 Web 应用,输入公司股票代码与年份,自动生成:

- ✅ **比率分析** — 盈利、运营、偿债、现金流(15+ 指标)
- ✅ **杜邦分析** — ROE 三因素分解(净利率 × 总资产周转率 × 权益乘数)
- ✅ **趋势分析** — 多年度交互式趋势图
- ✅ **同行业比较** — 对标公司柱状图 + 雷达图
- ✅ **基准分析** — 优秀/良好/一般/偏弱评级
- ✅ **中文报告** — 自动生成可下载 Markdown

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 📋 输入格式

| 市场 | 代码格式 | 例子 |
|------|---------|------|
| 美股 | 直接代码 | `AAPL`, `TSLA`, `MSFT` |
| 港股 | `代码.HK` | `0700.HK`(腾讯), `9988.HK`(阿里) |
| A 股(上海) | `代码.SS` | `600519.SS`(贵州茅台) |
| A 股(深圳) | `代码.SZ` | `000858.SZ`(五粮液) |
| 日股 | `代码.T` | `7203.T`(丰田) |
| 英股 | `代码.L` | `HSBA.L`(汇丰) |
| 德股 | `代码.DE` | `SAP.DE`(SAP) |

## 📁 项目结构

```
finance_agent/
├── app.py                    # Streamlit 主入口
├── requirements.txt          # 依赖
├── README.md
└── utils/
    ├── __init__.py
    ├── data_fetcher.py       # yfinance 数据抓取
    ├── ratios.py             # 比率计算 + 杜邦分析
    ├── benchmark.py          # 基准 + 同行对比
    ├── charts.py             # Plotly 图表
    └── report.py             # 中文报告生成
```

## 🔧 扩展方向

- **更换数据源**: 替换 `data_fetcher.py` 即可接入 Wind / Bloomberg / akshare
- **接入 LLM**: 在 `report.py` 中加入 Claude/GPT API,生成更深入的定性分析
- **行业特化基准**: 在 `benchmark.py` 中按 sector 细分基准值(如银行业、科技业各异)
- **加入预测**: 用 ARIMA / Prophet 对趋势做未来 1–2 年预测
- **多语言支持**: 报告中英双语切换

## ⚠️ 局限性

1. yfinance 是非官方接口,可能受 Yahoo Finance 限流影响
2. 部分小盘股、新上市公司、非美股公司财报字段可能缺失
3. 通用经验基准不能反映行业差异,请配合同行对比一同看
4. 本工具仅供学习参考,**不构成投资建议**

## 📝 License

MIT
