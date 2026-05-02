"""
财务分析 AI Agent - Streamlit 主入口
支持中英文切换,同行按"行业+规模"自动匹配
运行: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.data_fetcher import (
    fetch_company_info, fetch_financials,
    get_peer_suggestions_by_size, search_ticker_by_name, looks_like_ticker
)
from utils.ratios import (
    compute_ratios_for_year, compute_multi_year_ratios, dupont_analysis
)
from utils.benchmark import compare_with_peers, benchmark_analysis
from utils.charts import (
    plot_trend, plot_peer_comparison, plot_dupont_decomposition,
    plot_dupont_waterfall, plot_radar
)
from utils.report import generate_report
from utils.i18n import t


# ===== 页面配置 =====
st.set_page_config(
    page_title="Financial Analysis Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== 自定义样式 =====
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; max-width: 1300px; }
    h1 { color: #1f4e79; font-weight: 700; }
    h2 { color: #1f4e79; border-bottom: 2px solid #c00000; padding-bottom: 0.3rem; }
    h3 { color: #2c5282; }
    [data-testid="stMetricValue"] { font-size: 1.5rem; color: #1f4e79; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f5f7fa;
        border-radius: 6px 6px 0 0;
        padding: 8px 18px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f4e79;
        color: white;
    }
    .stAlert { border-left: 4px solid #1f4e79; }
</style>
""", unsafe_allow_html=True)


# ===== 语言选择 =====
if "lang" not in st.session_state:
    st.session_state.lang = "zh"

with st.sidebar:
    lang_choice = st.radio(
        "语言 / Language",
        options=["中文", "English"],
        index=0 if st.session_state.lang == "zh" else 1,
        horizontal=True,
        key="lang_radio",
    )
    st.session_state.lang = "zh" if lang_choice == "中文" else "en"
    st.markdown("---")

LANG = st.session_state.lang


# ===== 模式选择 =====
if "mode" not in st.session_state:
    st.session_state.mode = "ai"  # 默认 AI 对话

with st.sidebar:
    mode_label = "模式 / Mode" if LANG == "zh" else "Mode"
    mode_options = (["🤖 AI 对话", "📊 经典分析"] if LANG == "zh"
                    else ["🤖 AI Chat", "📊 Classic"])
    mode_choice = st.radio(
        mode_label, options=mode_options,
        index=0 if st.session_state.mode == "ai" else 1,
        key="mode_radio",
    )
    st.session_state.mode = "ai" if "AI" in mode_choice or "🤖" in mode_choice else "classic"
    st.markdown("---")

MODE = st.session_state.mode


# ===== 标题 =====
st.title(t("title", LANG))
st.caption(t("caption", LANG))


# ===== AI 对话模式 - 直接渲染聊天页面后退出 =====
if MODE == "ai":
    from utils.chat_page import render_chat_page
    render_chat_page(lang=LANG)
    st.stop()


# ===== 经典分析模式(下面是原有逻辑) =====



# ===== 侧边栏 — 输入 =====
with st.sidebar:
    st.header(t("sidebar_header", LANG))

    query = st.text_input(
        t("company_input_label", LANG),
        value="苹果" if LANG == "zh" else "Apple",
        placeholder=t("company_input_placeholder", LANG),
        help=t("company_input_help", LANG),
    ).strip()

    ticker = None
    if query:
        if looks_like_ticker(query):
            ticker = query.upper()
            st.caption(t("using_ticker", LANG, ticker=ticker))
        else:
            with st.spinner(t("search_company", LANG)):
                matches = search_ticker_by_name(query)
            if not matches:
                st.error(t("search_no_match", LANG, query=query))
            elif len(matches) == 1:
                m = matches[0]
                ticker = m["ticker"]
                st.success(t("search_one_match", LANG, name=m["name"], ticker=ticker))
            else:
                options = [f"{m['ticker']} — {m['name']} ({m.get('exchange','')})"
                           for m in matches]
                choice = st.selectbox(t("search_multi_match", LANG), options, index=0)
                ticker = choice.split(" — ")[0].strip()

    target_year = st.number_input(t("target_year", LANG),
                                    min_value=2010, max_value=2025, value=2024)
    num_years = st.slider(t("trend_years", LANG), min_value=2, max_value=8, value=5)
    if LANG == "zh":
        st.caption("💡 yfinance 通常仅提供近 4 年年报,实际显示年数可能少于此设置")
    else:
        st.caption("💡 yfinance usually provides ~4 years of annual data; actual range may be shorter")

    st.markdown("---")
    st.subheader(t("peer_section", LANG))
    peer_input = st.text_area(
        t("peer_input_label", LANG),
        value="",
        height=120,
        placeholder=t("peer_input_placeholder", LANG),
    )
    auto_peers = st.checkbox(t("auto_peers", LANG), value=True)

    st.markdown("---")
    run = st.button(t("run_button", LANG), type="primary", use_container_width=True)

    with st.expander(t("input_help_title", LANG)):
        st.markdown(t("input_help_content", LANG))


# ===== 主区 =====
if not run:
    st.info(t("welcome_msg", LANG))
    with st.expander(t("usage_title", LANG), expanded=True):
        st.markdown(t("usage_content", LANG))
    st.stop()

if not ticker:
    st.error(t("no_ticker_error", LANG))
    st.stop()


# ===== 执行分析 =====
with st.spinner(t("fetching_data", LANG, ticker=ticker)):
    info = fetch_company_info(ticker)
    financials = fetch_financials(ticker)

if "error" in info or financials.get("income", pd.DataFrame()).empty:
    st.error(t("fetch_failed", LANG, ticker=ticker))
    if "error" in info:
        st.code(info.get("error"))
    st.stop()


# ===== 公司卡片 =====
st.markdown(f"## {info['name']} ({info['ticker']})")

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("metric_sector", LANG), info.get("sector", "N/A"))
c2.metric(t("metric_industry", LANG), (info.get("industry") or "N/A")[:25])
c3.metric(t("metric_country", LANG), info.get("country", "N/A"))
mcap = info.get("market_cap")
mcap_str = f"{mcap/1e9:.1f}B {info.get('currency', 'USD')}" if mcap else "N/A"
c4.metric(t("metric_market_cap", LANG), mcap_str)

if info.get("summary"):
    with st.expander(t("company_summary", LANG)):
        st.write(info["summary"])

# ===== 选取目标年份 =====
income_df = financials["income"]
balance_df = financials["balance"]
cashflow_df = financials["cashflow"]

cols = sorted(income_df.columns, reverse=True)
cols_filtered = [c for c in cols if c.year <= target_year]
if not cols_filtered:
    st.error(t("year_not_found", LANG, target=target_year,
                avail=str([c.year for c in cols])))
    st.stop()

year_col = cols_filtered[0]
prev_col = cols_filtered[1] if len(cols_filtered) > 1 else None
actual_year = year_col.year

if actual_year != target_year:
    st.warning(t("year_fallback", LANG, target=target_year, actual=actual_year))


# ===== 计算 =====
ratios = compute_ratios_for_year(income_df, balance_df, cashflow_df, year_col, prev_col)
dupont = dupont_analysis(ratios)
trend_df = compute_multi_year_ratios(financials, target_year, num_years=num_years)


# ===== Tab 布局 =====
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    t("tab_overview", LANG), t("tab_dupont", LANG), t("tab_trend", LANG),
    t("tab_peer", LANG), t("tab_benchmark", LANG), t("tab_report", LANG),
])


# ===== Tab 1 =====
with tab1:
    st.subheader(t("year_metrics", LANG, year=actual_year))

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("ROE", f"{(ratios.get('ROE 净资产收益率') or 0)*100:.2f}%")
    cc2.metric("ROA", f"{(ratios.get('ROA 总资产收益率') or 0)*100:.2f}%")
    cc3.metric("Net Margin" if LANG == "en" else "净利率",
                f"{(ratios.get('净利率 (Net Margin)') or 0)*100:.2f}%")
    cc4.metric("Gross Margin" if LANG == "en" else "毛利率",
                f"{(ratios.get('毛利率 (Gross Margin)') or 0)*100:.2f}%")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Current Ratio" if LANG == "en" else "流动比率",
                f"{ratios.get('流动比率') or 0:.2f}")
    cc2.metric("Quick Ratio" if LANG == "en" else "速动比率",
                f"{ratios.get('速动比率') or 0:.2f}")
    cc3.metric("Debt/Assets" if LANG == "en" else "资产负债率",
                f"{(ratios.get('资产负债率') or 0)*100:.2f}%")
    cc4.metric("Asset Turnover" if LANG == "en" else "总资产周转率",
                f"{ratios.get('总资产周转率') or 0:.2f}")

    st.markdown("---")
    st.markdown(f"### {t('all_ratios', LANG)}")
    rows = []
    for k, v in ratios.items():
        if k.startswith("_"):
            continue
        is_pct = (any(kw in k for kw in ["ROE", "ROA", "ROIC", "Margin"]) or
                  ("率" in k and not any(x in k for x in ["流动比率", "速动比率", "周转率"])))
        if v is None:
            display = "N/A"
        elif is_pct:
            display = f"{v*100:.2f}%"
        elif abs(v) > 1e6:
            display = f"{v/1e6:.1f}M"
        else:
            display = f"{v:.3f}"
        rows.append({t("col_metric", LANG): k, t("col_value", LANG): display})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ===== Tab 2 =====
with tab2:
    st.subheader(t("dupont_title", LANG))
    st.latex(r"ROE = \text{Net Margin} \times \text{Asset Turnover} \times \text{Equity Multiplier}")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Net Margin" if LANG == "en" else "净利率",
                f"{(dupont.get('净利率') or 0)*100:.2f}%")
    cc2.metric("Asset Turnover" if LANG == "en" else "总资产周转率",
                f"{dupont.get('总资产周转率') or 0:.2f}")
    cc3.metric("Equity Multiplier" if LANG == "en" else "权益乘数",
                f"{dupont.get('权益乘数') or 0:.2f}")
    cc4.metric("ROE (DuPont)" if LANG == "en" else "ROE (杜邦)",
                f"{(dupont.get('ROE (杜邦计算)') or 0)*100:.2f}%")

    st.plotly_chart(plot_dupont_waterfall(dupont, actual_year), use_container_width=True)

    if trend_df is not None and not trend_df.empty:
        dupont_history = {}
        for col in trend_df.columns:
            yr_ratios = trend_df[col].to_dict()
            dupont_history[col] = {
                "净利率": yr_ratios.get("净利率 (Net Margin)"),
                "总资产周转率": yr_ratios.get("总资产周转率"),
                "权益乘数": yr_ratios.get("权益乘数 (Equity Multiplier)"),
                "ROE (杜邦计算)": yr_ratios.get("ROE 净资产收益率"),
            }
        st.plotly_chart(plot_dupont_decomposition(dupont_history),
                        use_container_width=True)


# ===== Tab 3 =====
with tab3:
    n = len(trend_df.columns) if not trend_df.empty else 0
    st.subheader(t("trend_title", LANG, n=n))

    # 提示用户实际可用年数 vs 请求的年数
    if n < num_years:
        if LANG == "zh":
            st.info(f"ℹ️ 你请求 {num_years} 年的数据,但 Yahoo Finance 对 {ticker} "
                    f"实际仅提供 {n} 年的年报。这是数据源的限制,不是代码问题。")
        else:
            st.info(f"ℹ️ You requested {num_years} years, but Yahoo Finance only "
                    f"provides {n} years of annual reports for {ticker}. "
                    f"This is a data-source limitation.")

    if trend_df.empty:
        st.warning(t("trend_data_insufficient", LANG))
    else:
        st.plotly_chart(plot_trend(trend_df,
            ["毛利率 (Gross Margin)", "营业利润率 (Operating Margin)", "净利率 (Net Margin)"],
            title=t("profitability_trend", LANG)), use_container_width=True)
        st.plotly_chart(plot_trend(trend_df,
            ["ROE 净资产收益率", "ROA 总资产收益率"],
            title=t("return_trend", LANG)), use_container_width=True)
        st.plotly_chart(plot_trend(trend_df,
            ["流动比率", "速动比率", "资产负债率"],
            title=t("solvency_trend", LANG)), use_container_width=True)

        with st.expander(t("trend_details", LANG)):
            def fmt_trend_cell(v, idx):
                is_pct = (any(kw in idx for kw in ["ROE", "ROA", "Margin"]) or
                          ("率" in idx and not any(x in idx for x in ["流动比率", "速动比率", "周转率"])))
                if pd.isna(v):
                    return "—"
                elif is_pct:
                    return f"{v*100:.2f}%"
                else:
                    return f"{v:.3f}"

            display_df = trend_df.copy().astype(object)
            for idx in display_df.index:
                for col in display_df.columns:
                    display_df.at[idx, col] = fmt_trend_cell(trend_df.loc[idx, col], idx)
            st.dataframe(display_df, use_container_width=True)


# ===== Tab 4: 同行对比(行业 + 规模匹配) =====
with tab4:
    st.subheader(t("peer_section_title", LANG))

    # 解析手动输入的同行
    raw_peers = [p.strip() for p in peer_input.split("\n") if p.strip()]
    peer_list = []
    failed_peers = []
    for p in raw_peers:
        if looks_like_ticker(p):
            peer_list.append(p.upper())
        else:
            matches = search_ticker_by_name(p)
            if matches:
                peer_list.append(matches[0]["ticker"])
            else:
                failed_peers.append(p)
    if failed_peers:
        st.warning(t("peer_unrecognized", LANG, names=", ".join(failed_peers)))

    # 自动建议(行业 + 规模)
    if not peer_list and auto_peers:
        spinner_msg = "Matching peers by industry & size..." if LANG == "en" else "正在按行业 + 规模匹配同行..."
        with st.spinner(spinner_msg):
            suggested = get_peer_suggestions_by_size(
                sector=info.get("sector", ""),
                target_market_cap=info.get("market_cap"),
                exclude=ticker,
                n=4,
            )
        peer_list = [s["ticker"] for s in suggested]

        if peer_list:
            peers_with_size = []
            for s in suggested:
                tk = s["ticker"]
                cap = s.get("market_cap")
                if cap:
                    if cap > 1e12:
                        size_str = f"{cap/1e12:.2f}T"
                    elif cap > 1e9:
                        size_str = f"{cap/1e9:.1f}B"
                    else:
                        size_str = f"{cap/1e6:.0f}M"
                    peers_with_size.append(f"{tk} ({size_str})")
                else:
                    peers_with_size.append(tk)
            st.info(t("auto_peer_msg", LANG,
                      sector=info.get("sector", "N/A"),
                      peers=", ".join(peers_with_size)))

    if not peer_list:
        st.warning(t("peer_warning", LANG))
    else:
        with st.spinner(t("fetching_peers", LANG, n=len(peer_list))):
            compare_df = compare_with_peers(ticker, peer_list, target_year)

        if compare_df.empty or len(compare_df.columns) < 2:
            st.error(t("peer_fetch_failed", LANG))
        else:
            key_metrics_for_chart = [
                "净利率 (Net Margin)", "ROE 净资产收益率",
                "ROA 总资产收益率", "资产负债率"
            ]
            for m in key_metrics_for_chart:
                if m in compare_df.index:
                    st.plotly_chart(plot_peer_comparison(compare_df, m),
                                    use_container_width=True)

            radar_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率",
                             "ROA 总资产收益率", "总资产周转率",
                             "毛利率 (Gross Margin)", "流动比率"]
            st.plotly_chart(plot_radar(compare_df, radar_metrics),
                            use_container_width=True)

            with st.expander(t("peer_details", LANG)):
                def fmt_peer_cell(v, idx):
                    is_pct = (any(kw in idx for kw in ["ROE", "ROA", "Margin"]) or
                              ("率" in idx and not any(x in idx for x in ["流动比率", "速动比率", "周转率"])))
                    if pd.isna(v):
                        return "—"
                    elif is_pct:
                        return f"{v*100:.2f}%"
                    else:
                        return f"{v:.3f}"

                display = compare_df.copy().astype(object)
                for idx in display.index:
                    for col in display.columns:
                        display.at[idx, col] = fmt_peer_cell(compare_df.loc[idx, col], idx)
                st.dataframe(display, use_container_width=True)

            st.session_state["compare_df"] = compare_df


# ===== Tab 5 =====
with tab5:
    st.subheader(t("benchmark_title", LANG))
    st.caption(t("benchmark_caption", LANG))

    bench_df = benchmark_analysis(ratios)
    if bench_df.empty:
        st.warning(t("no_benchmark_data", LANG))
    else:
        display_bench = bench_df.copy().astype(object)
        for idx, row in bench_df.iterrows():
            metric = row["指标"]
            is_pct = ("Margin" in metric or
                      ("率" in metric and not any(x in metric for x in ["流动比率", "速动比率", "周转率", "倍数"])))
            for col in ["公司值", "优秀基准", "良好基准", "一般基准"]:
                v = row[col]
                if pd.isna(v) or v is None:
                    display_bench.at[idx, col] = "—"
                elif is_pct:
                    display_bench.at[idx, col] = f"{v*100:.2f}%"
                else:
                    display_bench.at[idx, col] = f"{v:.2f}"
        st.dataframe(display_bench, use_container_width=True, hide_index=True)


# ===== Tab 6 - 增强报告(按章节:数据/图表 → AI 分析) =====
with tab6:
    st.subheader(t("report_title", LANG))

    compare_df = st.session_state.get("compare_df", pd.DataFrame())

    # 检查 API Key
    api_key = st.secrets.get("OPENAI_API_KEY", None) if hasattr(st, "secrets") else None
    if not api_key:
        with st.expander("🔑 OpenAI API Key (输入以启用 AI 深度分析)" if LANG == "zh"
                          else "🔑 OpenAI API Key"):
            api_key = st.text_input("API Key", type="password", key="report_api_key")

    # 缓存 key
    cache_key = f"{ticker}_{actual_year}_{len(compare_df.columns) if not compare_df.empty else 0}"

    if "report_cache" not in st.session_state:
        st.session_state.report_cache = {}
    cached = st.session_state.report_cache.get(cache_key)

    from utils.report_builder import (
        collect_all_charts, generate_section_analyses,
        build_html_report, build_docx_report, build_pdf_report
    )

    # === 第一阶段:收集图表 ===
    if cached is None or "charts" not in cached:
        with st.spinner("🎨 收集图表..." if LANG == "zh" else "🎨 Collecting charts..."):
            charts = collect_all_charts(ratios, dupont, trend_df, compare_df, actual_year)
        if cached is None:
            cached = {}
        cached["charts"] = charts
        st.session_state.report_cache[cache_key] = cached

    # === 第二阶段:LLM 生成分章节分析 ===
    if "sections" not in cached:
        if not api_key:
            st.warning("⚠️ 未配置 OpenAI API Key,使用基础规则报告(无 AI 深度解读)。"
                       "在 Streamlit Cloud Settings → Secrets 添加 `OPENAI_API_KEY`。"
                       if LANG == "zh" else
                       "⚠️ No API Key — using rule-based fallback.")
            # 兜底:用规则报告填充
            fallback = generate_report(info, ratios, dupont, trend_df, compare_df, actual_year)
            cached["sections"] = {
                "overview": "本公司基本信息见上表。",
                "profitability": fallback,
                "operating": "", "solvency": "", "dupont": "",
                "trend": "", "peer": "", "diagnosis": "",
            }
            cached["is_llm"] = False
        else:
            spinner_msg = ("🤖 AI 正在为各章节生成深度分析(约 15-40 秒)..."
                           if LANG == "zh" else "🤖 Generating AI analysis (15-40s)...")
            with st.spinner(spinner_msg):
                try:
                    sections = generate_section_analyses(
                        info, ratios, dupont, trend_df, compare_df,
                        actual_year, api_key,
                    )
                    cached["sections"] = sections
                    cached["is_llm"] = True
                except Exception as e:
                    st.error(f"AI 分析生成失败: {type(e).__name__}: {str(e)[:200]}")
                    fallback = generate_report(info, ratios, dupont, trend_df, compare_df, actual_year)
                    cached["sections"] = {
                        "overview": fallback, "profitability": "",
                        "operating": "", "solvency": "", "dupont": "",
                        "trend": "", "peer": "", "diagnosis": "",
                    }
                    cached["is_llm"] = False
        st.session_state.report_cache[cache_key] = cached

    sections = cached["sections"]
    charts = cached["charts"]

    # === UI 头部 ===
    col_a, col_b = st.columns([3, 1])
    with col_a:
        if cached.get("is_llm"):
            st.success("✅ AI 深度分析报告已生成" if LANG == "zh" else "✅ AI report ready")
        else:
            st.info("ℹ️ 当前为规则模板报告" if LANG == "zh" else "ℹ️ Rule-based report")
    with col_b:
        if st.button("🔄 重新生成" if LANG == "zh" else "🔄 Regenerate",
                      use_container_width=True, key="regen_report"):
            del st.session_state.report_cache[cache_key]
            st.rerun()

    st.markdown("---")

    # ========== 内联渲染:按章节"数据/图表 → AI 分析" ==========

    # 辅助:渲染特定 anchor 的所有图表
    def _render_anchor_charts(anchor):
        for ch in charts:
            if ch.get("section_anchor") == anchor:
                st.plotly_chart(ch["fig"], use_container_width=True,
                                key=f"sec_{ch['id']}")

    # 辅助:渲染指定指标子集的小表格
    def _render_subset_table(keys):
        rows = []
        for k in keys:
            v = ratios.get(k)
            if v is None and k not in ratios:
                continue
            is_pct = (any(kw in k for kw in ["ROE", "ROA", "ROIC", "Margin"]) or
                      ("率" in k and not any(x in k for x in ["流动比率", "速动比率", "周转率"])))
            if v is None:
                disp = "—"
            elif is_pct:
                disp = f"{v*100:.2f}%"
            elif abs(v) > 1e6:
                disp = f"{v/1e6:.1f}M"
            else:
                disp = f"{v:.3f}"
            rows.append({"指标": k, "数值": disp})
        if rows:
            st.table(pd.DataFrame(rows).set_index("指标"))

    profit_keys = ["毛利率 (Gross Margin)", "营业利润率 (Operating Margin)",
                   "净利率 (Net Margin)", "ROA 总资产收益率", "ROE 净资产收益率"]
    operating_keys = ["总资产周转率", "存货周转率", "应收账款周转率"]
    solvency_keys = ["流动比率", "速动比率", "资产负债率", "权益乘数 (Equity Multiplier)",
                     "利息保障倍数"]

    # ===== 一、公司概览 =====
    st.markdown("## 一、公司概览与行业地位")
    info_rows = [
        ("公司名称", info.get("name", "—")),
        ("股票代码", info.get("ticker", "—")),
        ("行业 / 子行业", f"{info.get('sector', '—')} / {info.get('industry', '—')}"),
        ("国家/地区", info.get("country", "—")),
        ("市值", f"{info.get('market_cap', 0)/1e9:.1f}B {info.get('currency', 'USD')}"
                  if info.get("market_cap") else "—"),
    ]
    st.table(pd.DataFrame(info_rows, columns=["项目", "内容"]).set_index("项目"))
    if sections.get("overview"):
        st.markdown(sections["overview"])

    # ===== 二、盈利能力 =====
    st.markdown("## 二、盈利能力分析")
    _render_anchor_charts("盈利")
    st.markdown("**核心盈利指标**")
    _render_subset_table(profit_keys)
    if sections.get("profitability"):
        st.markdown(sections["profitability"])

    # ===== 三、运营效率 =====
    st.markdown("## 三、运营效率")
    st.markdown("**运营效率指标**")
    _render_subset_table(operating_keys)
    if sections.get("operating"):
        st.markdown(sections["operating"])

    # ===== 四、偿债能力 =====
    st.markdown("## 四、偿债能力与财务结构")
    _render_anchor_charts("偿债")
    st.markdown("**偿债能力指标**")
    _render_subset_table(solvency_keys)
    if sections.get("solvency"):
        st.markdown(sections["solvency"])

    # ===== 五、杜邦分析 =====
    st.markdown("## 五、杜邦分析:ROE 驱动力拆解")
    _render_anchor_charts("杜邦")
    if sections.get("dupont"):
        st.markdown(sections["dupont"])

    # ===== 六、历年趋势 =====
    st.markdown("## 六、历年趋势与发展轨迹")
    _render_anchor_charts("趋势")
    if sections.get("trend"):
        st.markdown(sections["trend"])

    # ===== 七、同行业对标 =====
    st.markdown("## 七、同行业对标分析")
    if not compare_df.empty:
        st.markdown("**同行对照表**")
        # 简单对照表
        compare_display = compare_df.copy().astype(object)
        for idx in compare_display.index:
            is_pct = (any(kw in idx for kw in ["ROE", "ROA", "Margin"]) or
                      ("率" in idx and not any(x in idx for x in ["流动比率", "速动比率", "周转率"])))
            for col in compare_display.columns:
                v = compare_df.loc[idx, col]
                if pd.isna(v):
                    compare_display.loc[idx, col] = "—"
                elif is_pct:
                    compare_display.loc[idx, col] = f"{v*100:.2f}%"
                else:
                    compare_display.loc[idx, col] = f"{v:.3f}"
        st.dataframe(compare_display, use_container_width=True)
        _render_anchor_charts("同行")
    if sections.get("peer"):
        st.markdown(sections["peer"])

    # ===== 八、综合诊断 =====
    st.markdown("## 八、综合诊断与投资视角")
    if sections.get("diagnosis"):
        st.markdown(sections["diagnosis"])

    # === 下载选项 ===
    st.markdown("---")
    st.markdown("### 📥 下载报告" if LANG == "zh" else "### 📥 Download Report")

    fmt_col1, fmt_col2, fmt_col3, fmt_col4 = st.columns(4)

    # 拼接 Markdown 版本(章节 + 文字)
    titles_md = [
        ("一、公司概览与行业地位", "overview"),
        ("二、盈利能力分析", "profitability"),
        ("三、运营效率", "operating"),
        ("四、偿债能力与财务结构", "solvency"),
        ("五、杜邦分析:ROE 驱动力拆解", "dupont"),
        ("六、历年趋势与发展轨迹", "trend"),
        ("七、同行业对标分析", "peer"),
        ("八、综合诊断与投资视角", "diagnosis"),
    ]
    md_content = f"# {info['name']} ({ticker}) {actual_year} 年度财务分析报告\n\n"
    for title, key in titles_md:
        body = sections.get(key, "").strip()
        md_content += f"## {title}\n\n{body if body else '(本章节暂无分析)'}\n\n"

    with fmt_col1:
        st.download_button(
            "📄 Markdown",
            data=md_content,
            file_name=f"{ticker}_{actual_year}_财务分析.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with fmt_col2:
        try:
            html = build_html_report(info, actual_year, sections,
                                       charts, ratios, compare_df)
            st.download_button(
                "🌐 HTML",
                data=html.encode("utf-8"),
                file_name=f"{ticker}_{actual_year}_财务分析.html",
                mime="text/html",
                use_container_width=True,
            )
        except Exception as e:
            st.button("🌐 HTML (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True)

    with fmt_col3:
        try:
            docx_bytes = build_docx_report(info, actual_year, sections,
                                             charts, ratios, compare_df)
            st.download_button(
                "📝 Word",
                data=docx_bytes,
                file_name=f"{ticker}_{actual_year}_财务分析.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.button("📝 Word (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True)

    with fmt_col4:
        try:
            html_for_pdf = build_html_report(info, actual_year, sections,
                                               charts, ratios, compare_df)
            pdf_bytes = build_pdf_report(html_for_pdf)
            if pdf_bytes:
                st.download_button(
                    "📑 PDF",
                    data=pdf_bytes,
                    file_name=f"{ticker}_{actual_year}_财务分析.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.button("📑 PDF (不可用)", disabled=True,
                           help="服务器缺少 weasyprint,请改用 HTML 后在浏览器打印为 PDF",
                           use_container_width=True)
        except Exception as e:
            st.button("📑 PDF (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True)

    st.caption("💡 提示:HTML 文件可以在浏览器中按 Ctrl+P 直接打印为 PDF,中文显示最稳定。"
                if LANG == "zh" else
                "💡 Tip: HTML files can be printed to PDF via Ctrl+P in your browser.")
