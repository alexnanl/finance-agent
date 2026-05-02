"""
财务分析 AI Agent
Streamlit Web 应用主入口

运行方式:
    streamlit run app.py
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# 确保 utils 模块可被导入
sys.path.insert(0, str(Path(__file__).parent))

from utils.data_fetcher import (
    fetch_company_info, fetch_financials, get_peer_suggestions
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


# ===== 页面配置 =====
st.set_page_config(
    page_title="财务分析 Agent",
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


# ===== 标题 =====
st.title("📊 财务分析 AI Agent")
st.caption("输入公司代码与年份,自动生成比率分析、杜邦分析、趋势、同行对比与中文报告")

# ===== 侧边栏 — 输入 =====
with st.sidebar:
    st.header("⚙️ 分析参数")

    ticker = st.text_input(
        "公司股票代码",
        value="AAPL",
        help="美股直接输入(AAPL),港股加 .HK(0700.HK),A股加 .SS/.SZ(600519.SS)"
    ).strip().upper()

    target_year = st.number_input("目标年份", min_value=2010, max_value=2025, value=2024)

    num_years = st.slider("趋势分析年数", min_value=2, max_value=8, value=5)

    st.markdown("---")
    st.subheader("同行公司")
    peer_input = st.text_area(
        "同行代码(每行一个)",
        value="",
        height=120,
        placeholder="例如:\nMSFT\nGOOGL\n0700.HK"
    )
    auto_peers = st.checkbox("自动建议同行(根据行业)", value=True)

    st.markdown("---")
    run = st.button("🚀 开始分析", type="primary", use_container_width=True)

    with st.expander("ℹ️ 代码格式参考"):
        st.markdown("""
        - 美股: `AAPL`、`TSLA`、`MSFT`
        - 港股: `0700.HK`(腾讯)、`9988.HK`(阿里)
        - A股(上交所): `600519.SS`(贵州茅台)
        - A股(深交所): `000858.SZ`(五粮液)
        - 日股: `7203.T`(丰田)
        - 英股: `HSBA.L`(汇丰)
        """)


# ===== 主区域 =====
if not run:
    st.info("👈 在左侧输入公司代码与年份,点击「开始分析」")
    with st.expander("📖 使用说明", expanded=True):
        st.markdown("""
        ### 这个 Agent 能做什么?

        1. **比率分析** — 盈利、运营、偿债、现金流四大类共 15+ 个核心指标
        2. **杜邦分析** — ROE 三因素分解(净利率 × 总资产周转率 × 权益乘数)
        3. **趋势分析** — 多年度指标变化趋势 + 交互式图表
        4. **同行业比较** — 自动或手动指定同行,输出对比表与雷达图
        5. **基准分析** — 用通用经验阈值给每个指标打"优秀/良好/一般/偏弱"评级
        6. **中文报告** — 自动生成可下载的 Markdown 分析报告

        ### 数据来源
        Yahoo Finance(yfinance)— 覆盖全球主要交易所上市公司,免费、无需 Key。

        ### 局限性
        - 部分小盘股或非美股公司财报字段可能缺失
        - 经验基准为通用阈值,不同行业差异较大,请结合同行对比一同看
        - 当年财报需在 yfinance 已发布后才可分析
        """)
    st.stop()


# ===== 执行分析 =====
with st.spinner(f"📡 正在获取 {ticker} 的数据..."):
    info = fetch_company_info(ticker)
    financials = fetch_financials(ticker)

if "error" in info or financials.get("income", pd.DataFrame()).empty:
    st.error(f"❌ 无法获取 {ticker} 的数据。请确认代码是否正确(注意后缀 .HK / .SS / .SZ 等)。")
    if "error" in info:
        st.code(info.get("error"))
    st.stop()

# ===== 公司信息卡片 =====
st.markdown(f"## {info['name']} ({info['ticker']})")

c1, c2, c3, c4 = st.columns(4)
c1.metric("行业", info.get("sector", "N/A"))
c2.metric("子行业", (info.get("industry") or "N/A")[:25])
c3.metric("国家/地区", info.get("country", "N/A"))
mcap = info.get("market_cap")
mcap_str = f"{mcap/1e9:.1f}B {info.get('currency', 'USD')}" if mcap else "N/A"
c4.metric("市值", mcap_str)

if info.get("summary"):
    with st.expander("📝 公司简介"):
        st.write(info["summary"])

# ===== 选取目标年份的数据 =====
income_df = financials["income"]
balance_df = financials["balance"]
cashflow_df = financials["cashflow"]

cols = sorted(income_df.columns, reverse=True)
cols_filtered = [c for c in cols if c.year <= target_year]
if not cols_filtered:
    st.error(f"⚠️ 未找到 {target_year} 年或更早的财报数据。可用年份: "
             f"{[c.year for c in cols]}")
    st.stop()

year_col = cols_filtered[0]
prev_col = cols_filtered[1] if len(cols_filtered) > 1 else None
actual_year = year_col.year

if actual_year != target_year:
    st.warning(f"⚠️ {target_year} 年财报暂不可用,使用最近的 {actual_year} 年数据。")

# ===== 计算指标 =====
ratios = compute_ratios_for_year(income_df, balance_df, cashflow_df, year_col, prev_col)
dupont = dupont_analysis(ratios)
trend_df = compute_multi_year_ratios(financials, target_year, num_years=num_years)


# ===== Tab 布局 =====
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 比率总览", "🔻 杜邦分析", "📉 趋势", "🆚 同行对比", "🎯 基准", "📄 报告"
])

# ===== Tab 1: 比率总览 =====
with tab1:
    st.subheader(f"{actual_year} 年度核心指标")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("ROE", f"{(ratios.get('ROE 净资产收益率') or 0)*100:.2f}%")
    cc2.metric("ROA", f"{(ratios.get('ROA 总资产收益率') or 0)*100:.2f}%")
    cc3.metric("净利率", f"{(ratios.get('净利率 (Net Margin)') or 0)*100:.2f}%")
    cc4.metric("毛利率", f"{(ratios.get('毛利率 (Gross Margin)') or 0)*100:.2f}%")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("流动比率", f"{ratios.get('流动比率') or 0:.2f}")
    cc2.metric("速动比率", f"{ratios.get('速动比率') or 0:.2f}")
    cc3.metric("资产负债率", f"{(ratios.get('资产负债率') or 0)*100:.2f}%")
    cc4.metric("总资产周转率", f"{ratios.get('总资产周转率') or 0:.2f}")

    st.markdown("---")
    st.markdown("### 全部比率明细")

    # 把 ratios 整理为表格
    rows = []
    for k, v in ratios.items():
        if k.startswith("_"):
            continue
        is_pct = any(kw in k for kw in ["率", "ROE", "ROA", "ROIC", "Margin"]) \
                 and "周转率" not in k and "倍数" not in k
        if v is None:
            display = "N/A"
        elif is_pct:
            display = f"{v*100:.2f}%"
        elif abs(v) > 1e6:
            display = f"{v/1e6:.1f}M"
        else:
            display = f"{v:.3f}"
        rows.append({"指标": k, "数值": display})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ===== Tab 2: 杜邦分析 =====
with tab2:
    st.subheader("杜邦分析:ROE 三因素分解")
    st.latex(r"ROE = \text{净利率} \times \text{总资产周转率} \times \text{权益乘数}")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("净利率", f"{(dupont.get('净利率') or 0)*100:.2f}%")
    cc2.metric("总资产周转率", f"{dupont.get('总资产周转率') or 0:.2f}")
    cc3.metric("权益乘数", f"{dupont.get('权益乘数') or 0:.2f}")
    cc4.metric("ROE (杜邦)", f"{(dupont.get('ROE (杜邦计算)') or 0)*100:.2f}%")

    st.plotly_chart(plot_dupont_waterfall(dupont, actual_year), use_container_width=True)

    # 多年杜邦趋势
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


# ===== Tab 3: 趋势 =====
with tab3:
    st.subheader(f"近 {len(trend_df.columns) if not trend_df.empty else 0} 年趋势")

    if trend_df.empty:
        st.warning("趋势数据不足")
    else:
        # 盈利能力趋势
        st.plotly_chart(
            plot_trend(trend_df,
                       ["毛利率 (Gross Margin)", "营业利润率 (Operating Margin)",
                        "净利率 (Net Margin)"],
                       title="盈利能力趋势"),
            use_container_width=True
        )

        # 回报趋势
        st.plotly_chart(
            plot_trend(trend_df, ["ROE 净资产收益率", "ROA 总资产收益率"],
                       title="股东回报趋势"),
            use_container_width=True
        )

        # 偿债能力趋势
        st.plotly_chart(
            plot_trend(trend_df, ["流动比率", "速动比率", "资产负债率"],
                       title="偿债能力趋势"),
            use_container_width=True
        )

        # 数据表
        with st.expander("📋 趋势数据明细"):
            display_df = trend_df.copy()
            # 格式化
            for idx in display_df.index:
                is_pct = any(kw in idx for kw in ["率", "ROE", "ROA", "Margin"]) \
                         and "周转率" not in idx and "倍数" not in idx
                for col in display_df.columns:
                    v = display_df.loc[idx, col]
                    if pd.isna(v):
                        display_df.loc[idx, col] = "—"
                    elif is_pct:
                        display_df.loc[idx, col] = f"{v*100:.2f}%"
                    else:
                        display_df.loc[idx, col] = f"{v:.3f}"
            st.dataframe(display_df, use_container_width=True)


# ===== Tab 4: 同行对比 =====
with tab4:
    st.subheader("同行业比较")

    # 收集同行 ticker
    peer_list = [p.strip().upper() for p in peer_input.split("\n") if p.strip()]
    if not peer_list and auto_peers:
        peer_list = get_peer_suggestions(info.get("sector", ""), exclude=ticker)[:4]
        if peer_list:
            st.info(f"🤖 已自动选取同行: {', '.join(peer_list)}")

    if not peer_list:
        st.warning("请在侧边栏添加至少一个同行公司,或勾选「自动建议」")
    else:
        with st.spinner(f"获取同行数据 ({len(peer_list)} 家)..."):
            compare_df = compare_with_peers(ticker, peer_list, target_year)

        if compare_df.empty or len(compare_df.columns) < 2:
            st.error("同行数据获取失败,请检查代码")
        else:
            # 关键指标对比图
            key_metrics_for_chart = [
                "净利率 (Net Margin)", "ROE 净资产收益率",
                "ROA 总资产收益率", "资产负债率"
            ]
            for m in key_metrics_for_chart:
                if m in compare_df.index:
                    st.plotly_chart(plot_peer_comparison(compare_df, m),
                                    use_container_width=True)

            # 雷达图
            radar_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率",
                             "ROA 总资产收益率", "总资产周转率",
                             "毛利率 (Gross Margin)", "流动比率"]
            st.plotly_chart(plot_radar(compare_df, radar_metrics),
                            use_container_width=True)

            # 详细对比表
            with st.expander("📋 同行对比明细表"):
                display = compare_df.copy()
                for idx in display.index:
                    is_pct = any(kw in idx for kw in ["率", "ROE", "ROA", "Margin"]) \
                             and "周转率" not in idx and "倍数" not in idx
                    for col in display.columns:
                        v = display.loc[idx, col]
                        if pd.isna(v):
                            display.loc[idx, col] = "—"
                        elif is_pct:
                            display.loc[idx, col] = f"{v*100:.2f}%"
                        else:
                            display.loc[idx, col] = f"{v:.3f}"
                st.dataframe(display, use_container_width=True)

            # 保存到 session 供报告使用
            st.session_state["compare_df"] = compare_df


# ===== Tab 5: 基准 =====
with tab5:
    st.subheader("基准分析(经验阈值)")
    st.caption("⚠️ 通用经验阈值,行业差异大,请配合同行对比综合判断")

    bench_df = benchmark_analysis(ratios)
    if bench_df.empty:
        st.warning("无可对比的指标")
    else:
        # 格式化表格显示
        display_bench = bench_df.copy()
        for idx, row in display_bench.iterrows():
            metric = row["指标"]
            is_pct = any(kw in metric for kw in ["率", "Margin"]) \
                     and "周转率" not in metric and "倍数" not in metric
            for col in ["公司值", "优秀基准", "良好基准", "一般基准"]:
                v = row[col]
                if pd.isna(v) or v is None:
                    display_bench.at[idx, col] = "—"
                elif is_pct:
                    display_bench.at[idx, col] = f"{v*100:.2f}%"
                else:
                    display_bench.at[idx, col] = f"{v:.2f}"
        st.dataframe(display_bench, use_container_width=True, hide_index=True)


# ===== Tab 6: 报告 =====
with tab6:
    st.subheader("📄 中文分析报告")
    compare_df = st.session_state.get("compare_df", pd.DataFrame())
    report_md = generate_report(info, ratios, dupont, trend_df, compare_df, actual_year)

    st.markdown(report_md)

    st.markdown("---")
    st.download_button(
        "📥 下载报告 (Markdown)",
        data=report_md,
        file_name=f"{ticker}_{actual_year}_财务分析报告.md",
        mime="text/markdown",
        use_container_width=True,
    )
