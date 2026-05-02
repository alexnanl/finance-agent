"""
AI 对话模式页面 - 嵌入到 app.py 中
"""
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

    # ===== 检查 API Key =====
    api_key = st.secrets.get("OPENAI_API_KEY", None) if hasattr(st, "secrets") else None
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
                        fname = ev["filename"]
                        st.download_button(
                            f"📥 下载报告: {fname}",
                            data=ev["markdown"],
                            file_name=fname,
                            mime="text/markdown",
                            key=f"dl_{i}_{fname}",
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
                    fname = event["filename"]
                    st.download_button(
                        f"📥 下载报告: {fname}",
                        data=event["markdown"],
                        file_name=fname,
                        mime="text/markdown",
                        key=f"dl_new_{fname}_{len(st.session_state.chat_messages)}",
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
