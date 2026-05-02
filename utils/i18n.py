"""
界面多语言文案 (中文 / English)
"""

TRANSLATIONS = {
    "zh": {
        # 标题
        "title": "📊 财务分析 AI Agent",
        "caption": "输入公司名或股票代码,自动生成比率分析、杜邦分析、趋势、同行对比与中文报告",
        # 侧边栏
        "sidebar_header": "⚙️ 分析参数",
        "language": "语言 / Language",
        "company_input_label": "公司名 / 股票代码",
        "company_input_placeholder": "例:苹果、Apple、AAPL、腾讯、贵州茅台",
        "company_input_help": "支持中英文公司名,也可直接输入股票代码",
        "using_ticker": "📌 使用代码: **{ticker}**",
        "search_company": "🔍 搜索公司...",
        "search_no_match": "未找到「{query}」匹配的公司,请尝试英文名或股票代码",
        "search_one_match": "✅ {name} ({ticker})",
        "search_multi_match": "找到多个匹配,请选择:",
        "target_year": "目标年份",
        "trend_years": "趋势分析年数",
        "peer_section": "同行公司",
        "peer_input_label": "同行公司名(每行一个)",
        "peer_input_placeholder": "例如:\n微软\nGoogle\n腾讯",
        "auto_peers": "自动建议同行(按行业 + 规模)",
        "run_button": "🚀 开始分析",
        "input_help_title": "ℹ️ 输入示例",
        "input_help_content": """
        **公司名(中英文均可)**:
        - 苹果 / Apple → AAPL
        - 腾讯 / Tencent → 0700.HK
        - 贵州茅台 / Moutai → 600519.SS
        - 丰田 / Toyota → 7203.T

        **股票代码格式**:
        - 美股: `AAPL`、`TSLA`、`MSFT`
        - 港股: `0700.HK`、`9988.HK`
        - A股: `600519.SS`(沪)、`000858.SZ`(深)
        - 日股: `7203.T`,英股: `HSBA.L`
        """,
        # 主区
        "welcome_msg": "👈 在左侧输入公司名(如「苹果」「腾讯」「Tesla」)或股票代码,点击「开始分析」",
        "usage_title": "📖 使用说明",
        "usage_content": """
        ### 这个 Agent 能做什么?

        1. **比率分析** — 盈利、运营、偿债、现金流四大类共 15+ 个核心指标
        2. **杜邦分析** — ROE 三因素分解(净利率 × 总资产周转率 × 权益乘数)
        3. **趋势分析** — 多年度指标变化趋势 + 交互式图表
        4. **同行业比较** — 按行业 + 规模自动匹配同行
        5. **基准分析** — 用通用经验阈值给每个指标打"优秀/良好/一般/偏弱"评级
        6. **中文报告** — 自动生成可下载的 Markdown 分析报告

        ### 数据来源
        Yahoo Finance(yfinance)— 覆盖全球主要交易所上市公司,免费、无需 Key。
        """,
        "no_ticker_error": "❌ 请先在左侧输入有效的公司名或股票代码",
        "fetching_data": "📡 正在获取 {ticker} 的数据...",
        "fetch_failed": "❌ 无法获取 {ticker} 的数据。请确认代码是否正确(注意后缀 .HK / .SS / .SZ 等)。",
        # 公司卡片
        "metric_sector": "行业",
        "metric_industry": "子行业",
        "metric_country": "国家/地区",
        "metric_market_cap": "市值",
        "company_summary": "📝 公司简介",
        "year_fallback": "⚠️ {target} 年财报暂不可用,使用最近的 {actual} 年数据。",
        "year_not_found": "⚠️ 未找到 {target} 年或更早的财报数据。可用年份: {avail}",
        # Tab 标题
        "tab_overview": "📈 比率总览",
        "tab_dupont": "🔻 杜邦分析",
        "tab_trend": "📉 趋势",
        "tab_peer": "🆚 同行对比",
        "tab_benchmark": "🎯 基准",
        "tab_report": "📄 报告",
        # Tab 内容
        "year_metrics": "{year} 年度核心指标",
        "all_ratios": "全部比率明细",
        "dupont_title": "杜邦分析:ROE 三因素分解",
        "trend_title": "近 {n} 年趋势",
        "trend_data_insufficient": "趋势数据不足",
        "profitability_trend": "盈利能力趋势",
        "return_trend": "股东回报趋势",
        "solvency_trend": "偿债能力趋势",
        "trend_details": "📋 趋势数据明细",
        "peer_section_title": "同行业比较(按行业 + 规模匹配)",
        "auto_peer_msg": "🤖 已按「**{sector}** 行业 + 与目标公司同规模」自动选取: {peers}",
        "peer_unrecognized": "⚠️ 未能识别这些公司名: {names}",
        "peer_warning": "请在侧边栏添加至少一个同行公司,或勾选「自动建议」",
        "fetching_peers": "获取同行数据 ({n} 家)...",
        "peer_fetch_failed": "同行数据获取失败,请检查名称",
        "peer_details": "📋 同行对比明细表",
        "benchmark_title": "基准分析(经验阈值)",
        "benchmark_caption": "⚠️ 通用经验阈值,行业差异大,请配合同行对比综合判断",
        "no_benchmark_data": "无可对比的指标",
        "report_title": "📄 中文分析报告",
        "download_report": "📥 下载报告 (Markdown)",
        "report_filename": "{ticker}_{year}_财务分析报告.md",
        # 列名
        "col_metric": "指标",
        "col_value": "数值",
        "col_company_value": "公司值",
        "col_excellent": "优秀基准",
        "col_good": "良好基准",
        "col_fair": "一般基准",
        "col_rating": "评级",
        # 雷达图
        "radar_title": "综合能力雷达图(归一化)",
        "peer_avg": "同行均值",
    },
    "en": {
        "title": "📊 Financial Analysis AI Agent",
        "caption": "Enter a company name or ticker to generate ratio analysis, DuPont analysis, trends, peer comparison, and a Chinese report",
        "sidebar_header": "⚙️ Parameters",
        "language": "语言 / Language",
        "company_input_label": "Company Name / Ticker",
        "company_input_placeholder": "e.g., Apple, AAPL, Tencent, Toyota",
        "company_input_help": "Accepts Chinese/English company names or stock tickers",
        "using_ticker": "📌 Using ticker: **{ticker}**",
        "search_company": "🔍 Searching...",
        "search_no_match": "No match found for «{query}». Try English name or ticker.",
        "search_one_match": "✅ {name} ({ticker})",
        "search_multi_match": "Multiple matches — please select:",
        "target_year": "Target Year",
        "trend_years": "Years of Trend Data",
        "peer_section": "Peer Companies",
        "peer_input_label": "Peer company names (one per line)",
        "peer_input_placeholder": "e.g.\nMicrosoft\nGoogle\nTencent",
        "auto_peers": "Auto-suggest peers (by industry + size)",
        "run_button": "🚀 Run Analysis",
        "input_help_title": "ℹ️ Input Examples",
        "input_help_content": """
        **Company names (CN/EN)**:
        - Apple / 苹果 → AAPL
        - Tencent / 腾讯 → 0700.HK
        - Moutai / 贵州茅台 → 600519.SS
        - Toyota / 丰田 → 7203.T

        **Ticker formats**:
        - US: `AAPL`, `TSLA`, `MSFT`
        - HK: `0700.HK`, `9988.HK`
        - A-Shares: `600519.SS` (SH), `000858.SZ` (SZ)
        - JP: `7203.T`, UK: `HSBA.L`
        """,
        "welcome_msg": "👈 Enter a company name (e.g., Apple, Tesla) or ticker on the left, then click Run Analysis",
        "usage_title": "📖 What This Does",
        "usage_content": """
        ### Features

        1. **Ratio Analysis** — Profitability, efficiency, solvency, cash flow (15+ metrics)
        2. **DuPont Analysis** — ROE decomposition (Net Margin × Asset Turnover × Equity Multiplier)
        3. **Trend Analysis** — Multi-year trends with interactive charts
        4. **Peer Comparison** — Auto-matched by industry + market cap
        5. **Benchmark Analysis** — Excellent/Good/Fair/Weak ratings by generic thresholds
        6. **Chinese Report** — Auto-generated downloadable Markdown report

        ### Data Source
        Yahoo Finance via `yfinance` — covers major global exchanges, free, no API key.
        """,
        "no_ticker_error": "❌ Please enter a valid company name or ticker first",
        "fetching_data": "📡 Fetching data for {ticker}...",
        "fetch_failed": "❌ Could not fetch data for {ticker}. Check the ticker (suffix .HK / .SS / .SZ etc.).",
        "metric_sector": "Sector",
        "metric_industry": "Industry",
        "metric_country": "Country",
        "metric_market_cap": "Market Cap",
        "company_summary": "📝 Business Summary",
        "year_fallback": "⚠️ {target} fiscal data not yet available; using {actual}.",
        "year_not_found": "⚠️ No data found for {target} or earlier. Available: {avail}",
        "tab_overview": "📈 Overview",
        "tab_dupont": "🔻 DuPont",
        "tab_trend": "📉 Trends",
        "tab_peer": "🆚 Peers",
        "tab_benchmark": "🎯 Benchmark",
        "tab_report": "📄 Report",
        "year_metrics": "Key Metrics — FY{year}",
        "all_ratios": "All Ratios",
        "dupont_title": "DuPont: ROE Decomposition",
        "trend_title": "Last {n} Years Trends",
        "trend_data_insufficient": "Insufficient trend data",
        "profitability_trend": "Profitability Trends",
        "return_trend": "Return Trends",
        "solvency_trend": "Solvency Trends",
        "trend_details": "📋 Trend Data Details",
        "peer_section_title": "Peer Comparison (matched by industry + size)",
        "auto_peer_msg": "🤖 Auto-selected peers in **{sector}** with similar market cap: {peers}",
        "peer_unrecognized": "⚠️ Couldn't recognize: {names}",
        "peer_warning": "Add at least one peer company in the sidebar, or check 'Auto-suggest'",
        "fetching_peers": "Fetching peer data ({n} companies)...",
        "peer_fetch_failed": "Failed to fetch peer data. Check the names.",
        "peer_details": "📋 Peer Comparison Details",
        "benchmark_title": "Benchmark Analysis (rule-of-thumb thresholds)",
        "benchmark_caption": "⚠️ Generic thresholds — varies by industry. Use alongside peer comparison.",
        "no_benchmark_data": "No benchmark data available",
        "report_title": "📄 Analysis Report",
        "download_report": "📥 Download Report (Markdown)",
        "report_filename": "{ticker}_{year}_FinancialReport.md",
        "col_metric": "Metric",
        "col_value": "Value",
        "col_company_value": "Company",
        "col_excellent": "Excellent",
        "col_good": "Good",
        "col_fair": "Fair",
        "col_rating": "Rating",
        "radar_title": "Performance Radar (normalized)",
        "peer_avg": "Peer Avg",
    },
}


def t(key: str, lang: str = "zh", **kwargs) -> str:
    """获取翻译文本,支持 {占位符} 格式化"""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["zh"]).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
