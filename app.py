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


# ===== 标题 =====
st.title(t("title", LANG))
st.caption(t("caption", LANG))


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


# ===== Tab 6 =====
with tab6:
    st.subheader(t("report_title", LANG))
    compare_df = st.session_state.get("compare_df", pd.DataFrame())
    report_md = generate_report(info, ratios, dupont, trend_df, compare_df, actual_year)

    st.markdown(report_md)

    st.markdown("---")
    st.download_button(
        t("download_report", LANG),
        data=report_md,
        file_name=t("report_filename", LANG, ticker=ticker, year=actual_year),
        mime="text/markdown",
        use_container_width=True,
    )
