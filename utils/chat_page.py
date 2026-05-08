"""
AI 对话模式页面 - 嵌入到 app.py 中
"""
import os
import streamlit as st
import pandas as pd
from utils.ai_agent import chat_with_tools, estimate_tokens
from utils.charts import (
    plot_trend, plot_peer_comparison, plot_dupont_waterfall,
    plot_dupont_decomposition, plot_radar
)
from utils.data_fetcher import fetch_financials, fetch_company_info
from utils.ratios import compute_multi_year_ratios, compute_ratios_for_year, dupont_analysis
from utils.benchmark import compare_with_peers


# 防滥用:每个会话最大消息数
MAX_MESSAGES_PER_SESSION = 60
MAX_INPUT_LENGTH = 1000


def _render_report_download_buttons(ev: dict, key_prefix: str, api_key: str = None):
    """
    渲染 4 种格式的下载按钮(Markdown / HTML / Word / PDF)。
    用经典模式同样的 build_*_report 函数,确保 AI 对话模式与经典模式报告完全一致。

    ev 是 {"type": "report", "filename", "markdown", "ticker", "year", "full_data"}
    full_data 是 {"info", "ratios", "dupont", "trend_df", "compare_df", "actual_year", "ticker"}
    """
    fname_md = ev.get("filename") or "report.md"
    md_content = ev.get("markdown", "")
    full_data = ev.get("full_data")
    ticker = ev.get("ticker", "report")
    year = ev.get("year", 2024)
    base_name = f"{ticker}_{year}_财务分析"

    # 如果没有 full_data(老的历史消息 / 数据缺失),只能用简版 Markdown
    if not full_data:
        st.download_button(
            f"📥 下载 Markdown: {fname_md}",
            data=md_content if md_content else "(报告内容为空,请重新生成)",
            file_name=fname_md,
            mime="text/markdown",
            key=f"{key_prefix}_md_only",
            disabled=not bool(md_content),
        )
        if not md_content:
            st.warning("⚠️ 报告内容为空。请重新发起请求(例如:『给我特斯拉的完整报告』)。")
        return

    # 有完整数据,生成 4 种格式
    info = full_data["info"]
    ratios = full_data["ratios"]
    dupont = full_data["dupont"]
    trend_df = full_data["trend_df"]
    compare_df = full_data["compare_df"]
    actual_year = full_data["actual_year"]

    # 缓存 sections 和 charts(避免每次渲染都重新生成 = 重新 LLM 调用)
    cache_key = f"chat_report_{ticker}_{actual_year}"
    if "report_cache" not in st.session_state:
        st.session_state.report_cache = {}

    cached = st.session_state.report_cache.get(cache_key)

    # --- 第一阶段:收集图表 ---
    from utils.report_builder import (
        collect_all_charts, generate_section_analyses,
        build_html_report, build_docx_report, build_pdf_report
    )

    if cached is None or "charts" not in cached:
        with st.spinner("🎨 准备图表..."):
            charts = collect_all_charts(ratios, dupont, trend_df, compare_df, actual_year)
        if cached is None:
            cached = {}
        cached["charts"] = charts
        st.session_state.report_cache[cache_key] = cached

    # --- 第二阶段:LLM 生成 8 章节深度分析(与经典模式相同的函数) ---
    if "sections" not in cached:
        if not api_key:
            # 兜底:用规则报告(简版 Markdown)
            cached["sections"] = {
                "overview": md_content or "本公司基本信息见上表。",
                "profitability": "", "operating": "", "solvency": "", "dupont": "",
                "trend": "", "peer": "", "diagnosis": "",
            }
            cached["is_llm"] = False
        else:
            with st.spinner("🤖 AI 正在为各章节生成深度分析(约 15-40 秒)..."):
                try:
                    sections = generate_section_analyses(
                        info, ratios, dupont, trend_df, compare_df,
                        actual_year, api_key,
                    )
                    cached["sections"] = sections
                    cached["is_llm"] = True
                except Exception as e:
                    st.warning(f"⚠️ AI 章节生成失败({type(e).__name__}),降级为简版报告")
                    cached["sections"] = {
                        "overview": md_content or "本公司基本信息见上表。",
                        "profitability": "", "operating": "", "solvency": "", "dupont": "",
                        "trend": "", "peer": "", "diagnosis": "",
                    }
                    cached["is_llm"] = False
        st.session_state.report_cache[cache_key] = cached

    sections = cached["sections"]
    charts = cached["charts"]

    if cached.get("is_llm"):
        st.success("✅ AI 深度分析报告已生成,选择下载格式:")
    else:
        st.info("ℹ️ 当前为简版报告(未配置 API Key 或 AI 调用失败)")

    # ===== 4 个下载按钮 =====
    fmt_col1, fmt_col2, fmt_col3, fmt_col4 = st.columns(4)

    with fmt_col1:
        # Markdown:把所有章节拼起来
        full_md_parts = [f"# {info.get('name', ticker)} ({ticker}) — {actual_year} 年财务分析\n"]
        section_titles = [
            ("overview", "公司概览"),
            ("profitability", "盈利能力"),
            ("operating", "运营效率"),
            ("solvency", "偿债能力"),
            ("dupont", "杜邦分析"),
            ("trend", "历年趋势"),
            ("peer", "同行对标"),
            ("diagnosis", "综合诊断"),
        ]
        for skey, stitle in section_titles:
            content = sections.get(skey, "")
            if content:
                full_md_parts.append(f"\n## {stitle}\n\n{content}\n")
        full_md = "\n".join(full_md_parts)

        st.download_button(
            "📄 Markdown",
            data=full_md,
            file_name=f"{base_name}.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"{key_prefix}_md",
        )

    with fmt_col2:
        try:
            html = build_html_report(info, actual_year, sections,
                                       charts, ratios, compare_df)
            st.download_button(
                "🌐 HTML",
                data=html.encode("utf-8"),
                file_name=f"{base_name}.html",
                mime="text/html",
                use_container_width=True,
                key=f"{key_prefix}_html",
            )
        except Exception as e:
            st.button("🌐 HTML (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True,
                       key=f"{key_prefix}_html_fail")

    with fmt_col3:
        try:
            docx_bytes = build_docx_report(info, actual_year, sections,
                                             charts, ratios, compare_df)
            st.download_button(
                "📝 Word",
                data=docx_bytes,
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"{key_prefix}_docx",
            )
        except Exception as e:
            st.button("📝 Word (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True,
                       key=f"{key_prefix}_docx_fail")

    with fmt_col4:
        try:
            html_for_pdf = build_html_report(info, actual_year, sections,
                                               charts, ratios, compare_df)
            pdf_bytes = build_pdf_report(html_for_pdf)
            if pdf_bytes:
                st.download_button(
                    "📑 PDF",
                    data=pdf_bytes,
                    file_name=f"{base_name}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"{key_prefix}_pdf",
                )
            else:
                st.button("📑 PDF (不可用)", disabled=True,
                           help="服务器缺少 weasyprint,请改用 HTML 后在浏览器打印为 PDF",
                           use_container_width=True,
                           key=f"{key_prefix}_pdf_unavail")
        except Exception as e:
            st.button("📑 PDF (失败)", disabled=True,
                       help=f"{type(e).__name__}: {str(e)[:100]}",
                       use_container_width=True,
                       key=f"{key_prefix}_pdf_fail")


def render_tool_visual(tool_name: str, args: dict, result: dict):
    """根据工具调用结果,渲染对应的可视化"""
    if "error" in result:
        return  # 错误不渲染图表

    company = args.get("company", "")
    year = args.get("year", 2024)

    try:
        if tool_name == "dupont_analysis":
            ticker = result.get("ticker")
            if not ticker:
                return
            dp = {
                "净利率": result.get("净利率 (Net Margin)"),
                "总资产周转率": result.get("总资产周转率 (Asset Turnover)"),
                "权益乘数": result.get("权益乘数 (Equity Multiplier)"),
                "ROE (杜邦计算)": result.get("ROE (杜邦计算)"),
            }
            st.plotly_chart(plot_dupont_waterfall(dp, result.get("year", year)),
                            use_container_width=True, key=f"dupont_{ticker}_{year}")

        elif tool_name == "trend_analysis":
            ticker = result.get("ticker")
            if not ticker:
                return
            num_years = args.get("num_years", 5)
            target_year = args.get("target_year", 2024)
            fin = fetch_financials(ticker)
            trend_df = compute_multi_year_ratios(fin, target_year, num_years=num_years)
            if not trend_df.empty:
                st.plotly_chart(
                    plot_trend(trend_df,
                                ["毛利率 (Gross Margin)", "营业利润率 (Operating Margin)",
                                 "净利率 (Net Margin)"],
                                title="盈利能力趋势"),
                    use_container_width=True,
                    key=f"trend_prof_{ticker}_{num_years}"
                )
                st.plotly_chart(
                    plot_trend(trend_df,
                                ["ROE 净资产收益率", "ROA 总资产收益率"],
                                title="股东回报趋势"),
                    use_container_width=True,
                    key=f"trend_ret_{ticker}_{num_years}"
                )

        elif tool_name == "peer_comparison":
            ticker = result.get("ticker")
            peers = result.get("peers_used", [])
            if ticker and peers:
                compare_df = compare_with_peers(ticker, peers, year)
                if not compare_df.empty:
                    for m in ["净利率 (Net Margin)", "ROE 净资产收益率"]:
                        if m in compare_df.index:
                            st.plotly_chart(
                                plot_peer_comparison(compare_df, m),
                                use_container_width=True,
                                key=f"peer_{m}_{ticker}_{year}"
                            )

        elif tool_name == "compute_ratios":
            ratios_data = result.get("ratios", {})
            if ratios_data:
                # 4 列关键指标
                key_metrics_pct = [
                    ("ROE", "ROE 净资产收益率"),
                    ("ROA", "ROA 总资产收益率"),
                    ("净利率", "净利率 (Net Margin)"),
                    ("毛利率", "毛利率 (Gross Margin)"),
                ]
                cols = st.columns(4)
                for col, (label, key) in zip(cols, key_metrics_pct):
                    val = ratios_data.get(key, {}).get("value")
                    if val is not None:
                        col.metric(label, f"{val*100:.2f}%")
    except Exception as e:
        st.caption(f"_(图表渲染跳过: {e})_")


def render_chat_page(lang: str = "zh"):
    """渲染 AI 对话页面"""

    # ===== 检查 API Key(兼容 Streamlit Cloud secrets + HF Spaces 环境变量)=====
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        api_key = None
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # 允许用户自己输入(开发/备选模式)
        with st.expander("🔑 OpenAI API Key (开发者备选)" if lang == "zh"
                          else "🔑 OpenAI API Key (developer fallback)"):
            api_key = st.text_input(
                "OpenAI API Key", type="password",
                help="如果你没有部署的 API Key,可临时用自己的。仅本会话有效。"
            )

    if not api_key:
        if lang == "zh":
            st.error("❌ 当前应用未配置 OpenAI API Key。请在 Streamlit Secrets 中添加 "
                     "`OPENAI_API_KEY`,或在上方输入框临时填入。")
            st.markdown("""
            **管理员配置方法**:
            1. 在 Streamlit Cloud 应用设置中找到 Settings → Secrets
            2. 添加一行: `OPENAI_API_KEY = "sk-..."`
            3. 保存后应用会自动重启
            """)
        else:
            st.error("❌ OpenAI API Key not configured. Add `OPENAI_API_KEY` to Streamlit Secrets.")
        return

    # ===== 初始化对话历史 =====
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "generated_reports" not in st.session_state:
        st.session_state.generated_reports = {}  # filename -> markdown

    # ===== 工具栏 =====
    col1, col2 = st.columns([5, 1])
    with col1:
        if lang == "zh":
            st.markdown("""
            💡 **使用示例**:
            - "苹果 2024 年怎么样" → 简单评估
            - "杜邦分析一下茅台" → 单项深入
            - "腾讯和阿里巴巴比一下" → 同行对比
            - "给我特斯拉的完整分析报告" → 下载报告
            """)
        else:
            st.markdown("""
            💡 **Examples**:
            - "How is Apple doing in 2024?" → quick assessment
            - "Run a DuPont analysis on Microsoft" → deep dive
            - "Compare Tesla with Ford" → peer comparison
            - "Generate a full report for NVIDIA" → downloadable report
            """)
    with col2:
        if st.button("🗑️ 清空对话" if lang == "zh" else "🗑️ Clear", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.generated_reports = {}
            st.rerun()

    st.markdown("---")

    # ===== 渲染历史消息 =====
    for i, msg in enumerate(st.session_state.chat_messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                # assistant 消息可能附带工具事件序列
                events = msg.get("events", [])
                for ev in events:
                    if ev["type"] == "tool_call":
                        with st.expander(f"🔧 调用工具: `{ev['tool']}`", expanded=False):
                            st.json(ev.get("args", {}))
                    elif ev["type"] == "tool_visual":
                        # 重渲染图表
                        render_tool_visual(ev["tool"], ev["args"], ev["result"])
                    elif ev["type"] == "report":
                        _render_report_download_buttons(
                            ev,
                            key_prefix=f"hist_{i}",
                            api_key=api_key,
                        )

                if msg.get("content"):
                    st.markdown(msg["content"])

    # ===== 输入框 =====
    if len(st.session_state.chat_messages) >= MAX_MESSAGES_PER_SESSION:
        st.warning(f"⚠️ 本会话已达 {MAX_MESSAGES_PER_SESSION} 条消息上限,请清空对话后继续。"
                   if lang == "zh" else
                   f"⚠️ Session limit reached ({MAX_MESSAGES_PER_SESSION}). Clear to continue.")
        return

    user_input = st.chat_input(
        "问我任何关于上市公司财务的问题..." if lang == "zh"
        else "Ask anything about public companies' financials..."
    )

    if not user_input:
        return

    if len(user_input) > MAX_INPUT_LENGTH:
        st.error(f"输入过长(>{MAX_INPUT_LENGTH} 字),请精简后重发"
                 if lang == "zh" else
                 f"Input too long (>{MAX_INPUT_LENGTH} chars).")
        return

    # 显示用户消息
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 构造给 LLM 的对话历史(只取必要字段,不带 events)
    llm_messages = []
    for m in st.session_state.chat_messages:
        if m["role"] == "user":
            llm_messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant" and m.get("content"):
            llm_messages.append({"role": "assistant", "content": m["content"]})

    # ===== 流式调用 Agent =====
    with st.chat_message("assistant"):
        events_log = []  # 记录用于回放历史
        final_content = ""
        status_placeholder = st.empty()

        try:
            for event in chat_with_tools(llm_messages, api_key=api_key):
                if event["type"] == "tool_call":
                    status_placeholder.info(f"🔧 调用 `{event['tool']}` ...")
                    events_log.append(event)
                    with st.expander(f"🔧 调用工具: `{event['tool']}`", expanded=False):
                        st.json(event.get("args", {}))

                elif event["type"] == "tool_result":
                    # 找到对应的 call,把 result 合并进去用于渲染
                    if events_log and events_log[-1].get("type") == "tool_call":
                        call_event = events_log[-1]
                        visual_event = {
                            "type": "tool_visual",
                            "tool": call_event["tool"],
                            "args": call_event["args"],
                            "result": event["result"],
                        }
                        events_log.append(visual_event)
                        render_tool_visual(call_event["tool"], call_event["args"],
                                            event["result"])

                elif event["type"] == "report":
                    events_log.append(event)
                    _render_report_download_buttons(
                        event,
                        key_prefix=f"new_{len(st.session_state.chat_messages)}",
                        api_key=api_key,
                    )

                elif event["type"] == "assistant":
                    final_content = event["content"]
                    status_placeholder.empty()
                    st.markdown(final_content)

                elif event["type"] == "error":
                    status_placeholder.empty()
                    st.error(event["message"])
                    final_content = f"⚠️ {event['message']}"

        except Exception as e:
            status_placeholder.empty()
            st.error(f"对话出错: {type(e).__name__}: {str(e)[:200]}")
            final_content = f"⚠️ 出错: {str(e)[:100]}"

    # 保存到历史
    st.session_state.chat_messages.append({
        "role": "assistant",
        "content": final_content,
        "events": events_log,
    })
