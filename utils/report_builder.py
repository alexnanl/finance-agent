"""
增强报告生成器
- 把 Plotly 图表渲染成 PNG(嵌入 HTML/PDF/DOCX)
- 调用 LLM 生成基于所有数据的详细分析
- 支持 Markdown / HTML / PDF / DOCX 四种格式
"""
import base64
import io
import json
from typing import Dict, List, Optional, Tuple
import pandas as pd

from utils.charts import (
    plot_trend, plot_dupont_waterfall, plot_dupont_decomposition,
    plot_peer_comparison, plot_radar
)


# ============================================================
# 图表 → PNG (base64)
# ============================================================
def fig_to_png_base64(fig, width: int = 900, height: int = 450) -> Optional[str]:
    """把 Plotly 图表转换成 base64 PNG 字符串。失败返回 None。"""
    try:
        png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        return base64.b64encode(png_bytes).decode("utf-8")
    except Exception:
        # kaleido 没装 / 转换失败时返回 None,后续逻辑跳过
        return None


def fig_to_png_bytes(fig, width: int = 900, height: int = 450) -> Optional[bytes]:
    """图表转 PNG bytes(用于 docx 嵌入)"""
    try:
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None


# ============================================================
# 收集所有图表
# ============================================================
def collect_all_charts(ratios: Dict, dupont: Dict, trend_df: pd.DataFrame,
                        compare_df: pd.DataFrame, year: int) -> List[Dict]:
    """
    生成所有图表对象,返回:
    [{"id": "trend_profit", "title": "盈利能力趋势", "fig": <plotly Figure>}, ...]
    """
    charts = []

    # 1. 杜邦瀑布图
    charts.append({
        "id": "dupont_waterfall",
        "title": f"{year} 年杜邦三因素分解",
        "category": "杜邦分析",
        "fig": plot_dupont_waterfall(dupont, year),
    })

    # 2. 杜邦多年趋势
    if not trend_df.empty:
        dupont_history = {}
        for col in trend_df.columns:
            yr = trend_df[col].to_dict()
            dupont_history[col] = {
                "净利率": yr.get("净利率 (Net Margin)"),
                "总资产周转率": yr.get("总资产周转率"),
                "权益乘数": yr.get("权益乘数 (Equity Multiplier)"),
                "ROE (杜邦计算)": yr.get("ROE 净资产收益率"),
            }
        charts.append({
            "id": "dupont_trend",
            "title": "杜邦三因素历年趋势",
            "category": "杜邦分析",
            "fig": plot_dupont_decomposition(dupont_history),
        })

    # 3-5. 三类趋势图
    if not trend_df.empty:
        charts.append({
            "id": "trend_profit",
            "title": "盈利能力趋势",
            "category": "趋势分析",
            "fig": plot_trend(trend_df,
                ["毛利率 (Gross Margin)", "营业利润率 (Operating Margin)",
                 "净利率 (Net Margin)"], title="盈利能力趋势"),
        })
        charts.append({
            "id": "trend_return",
            "title": "股东回报趋势",
            "category": "趋势分析",
            "fig": plot_trend(trend_df,
                ["ROE 净资产收益率", "ROA 总资产收益率"], title="股东回报趋势"),
        })
        charts.append({
            "id": "trend_solvency",
            "title": "偿债能力趋势",
            "category": "趋势分析",
            "fig": plot_trend(trend_df,
                ["流动比率", "速动比率", "资产负债率"], title="偿债能力趋势"),
        })

    # 6-9. 同行对比柱状图 + 雷达
    if not compare_df.empty and len(compare_df.columns) >= 2:
        for m in ["净利率 (Net Margin)", "ROE 净资产收益率",
                  "ROA 总资产收益率", "资产负债率"]:
            if m in compare_df.index:
                charts.append({
                    "id": f"peer_{m}",
                    "title": f"同行对比: {m}",
                    "category": "同行对比",
                    "fig": plot_peer_comparison(compare_df, m),
                })

        radar_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率",
                         "ROA 总资产收益率", "总资产周转率",
                         "毛利率 (Gross Margin)", "流动比率"]
        charts.append({
            "id": "radar",
            "title": "综合能力雷达图",
            "category": "同行对比",
            "fig": plot_radar(compare_df, radar_metrics),
        })

    return charts


# ============================================================
# 调用 LLM 生成深度分析
# ============================================================
def generate_llm_analysis(company_info: Dict, ratios: Dict, dupont: Dict,
                            trend_df: pd.DataFrame, compare_df: pd.DataFrame,
                            year: int, api_key: str,
                            model: str = "gpt-4o-mini") -> str:
    """调用 LLM 基于所有数据生成专业的中文深度分析"""
    from openai import OpenAI

    # 准备喂给 LLM 的结构化数据
    def clean_ratios(d):
        return {k: round(v, 4) if v is not None else None
                for k, v in d.items() if not k.startswith("_")}

    data_summary = {
        "公司": {
            "名称": company_info.get("name"),
            "代码": company_info.get("ticker"),
            "行业": company_info.get("sector"),
            "子行业": company_info.get("industry"),
            "国家": company_info.get("country"),
            "市值": company_info.get("market_cap"),
            "币种": company_info.get("currency"),
        },
        "财年": year,
        "比率": clean_ratios(ratios),
        "杜邦分解": {k: round(v, 4) if v else None for k, v in dupont.items()},
    }

    # 趋势数据
    if not trend_df.empty:
        trend_dict = {}
        for idx in trend_df.index:
            trend_dict[idx] = {str(c): round(v, 4) if pd.notna(v) else None
                                for c, v in trend_df.loc[idx].items()}
        data_summary["历年趋势"] = trend_dict

    # 同行数据
    if not compare_df.empty:
        peer_dict = {}
        for idx in compare_df.index:
            peer_dict[idx] = {str(c): round(v, 4) if pd.notna(v) else None
                                for c, v in compare_df.loc[idx].items()}
        data_summary["同行对比"] = peer_dict

    system_prompt = """你是一名资深的财务分析师,擅长基于上市公司财务数据撰写专业、深入、有洞察力的中文分析报告。

# 写作要求
- **严谨专业**:用财会术语,但不晦涩
- **深度洞察**:不只罗列数字,要解释"为什么"、"意味着什么"、"对投资者意味着什么"
- **结构清晰**:用 ## 二级标题分章节,## 下用 ### 三级标题
- **数据驱动**:每个判断都要用具体数字支持
- **批判性思维**:既看到亮点,也指出风险和异常
- **行业语境**:结合该行业特性解读(如银行业杠杆高很正常)
- **历史对比**:利用历年趋势数据指出方向性变化
- **同行参照**:利用同行对比数据指出相对优劣

# 报告结构(必须包含这些章节)
## 一、公司概览与行业地位
## 二、盈利能力深度分析
## 三、运营效率分析
## 四、偿债能力与财务结构
## 五、杜邦分析:ROE 驱动力拆解
## 六、历年趋势与发展轨迹
## 七、同行业对标分析
## 八、综合诊断与投资视角
   ### 优势
   ### 风险与不足
   ### 投资者关注要点

# 重要约束
- **绝对**不要在报告中说"图表显示"、"如图所示"等表述,因为这是文字版本,后续会插入图表
- 绝对不要使用 Markdown 表格(报告会另外插入数据表)
- 不要重复堆砌相同的数据多次
- 篇幅:1500-2500 字之间(不算空行)
- 用具体数字而非模糊词,例如"ROE 22.5%"不要写"ROE 较高"
- 如某项数据缺失(N/A),不要捏造,跳过即可"""

    user_prompt = f"""请基于以下数据,撰写一份关于 **{data_summary['公司']['名称']}** \
({data_summary['公司']['代码']}) {year} 年度的专业财务分析报告。

# 完整数据
```json
{json.dumps(data_summary, ensure_ascii=False, indent=2)}
```

请直接输出 Markdown 格式的报告内容(不要有 ```markdown 代码块包裹),从 ## 一、公司概览与行业地位 开始。"""

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )
    return resp.choices[0].message.content or ""


# ============================================================
# HTML 报告
# ============================================================
HTML_CSS = """
<style>
  body {
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
    max-width: 920px;
    margin: 32px auto;
    padding: 24px;
    color: #222;
    line-height: 1.7;
    background: #fff;
  }
  h1 { color: #1f4e79; border-bottom: 3px solid #c00000; padding-bottom: 12px; }
  h2 { color: #1f4e79; border-left: 4px solid #c00000; padding-left: 12px;
        margin-top: 36px; }
  h3 { color: #2c5282; margin-top: 24px; }
  .meta { color: #555; font-size: 14px; margin-bottom: 24px; }
  .chart-block { margin: 24px 0; text-align: center; }
  .chart-block img { max-width: 100%; height: auto;
                       border: 1px solid #e5e7eb; border-radius: 6px; }
  .chart-caption { font-size: 13px; color: #666; margin-top: 6px; font-style: italic; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f5f7fa; color: #1f4e79; }
  tr:nth-child(even) { background: #fafbfc; }
  .summary-box { background: #f5f7fa; border-left: 4px solid #1f4e79;
                  padding: 16px 20px; margin: 20px 0; border-radius: 4px; }
  .footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #eee;
              color: #888; font-size: 12px; text-align: center; }
  ul { padding-left: 24px; }
  li { margin: 6px 0; }
  strong { color: #1f4e79; }
</style>
"""


def md_to_html(md: str) -> str:
    """轻量 Markdown 转 HTML(只处理基本元素)"""
    import re
    lines = md.split("\n")
    out = []
    in_list = False
    for line in lines:
        line = line.rstrip()
        if not line:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue
        # 标题
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue
        # 列表
        m_li = re.match(r"^[-*]\s+(.+)", line)
        if m_li:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline_md(m_li.group(1))}</li>")
            continue
        # 普通段落
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{_inline_md(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline_md(text: str) -> str:
    """处理 **bold** *italic* `code`"""
    import re
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^\*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def build_html_report(company_info: Dict, year: int, llm_analysis: str,
                       charts: List[Dict], ratios: Dict,
                       compare_df: pd.DataFrame) -> str:
    """构建完整 HTML 报告"""
    name = company_info.get("name", "Company")
    ticker = company_info.get("ticker", "")
    sector = company_info.get("sector", "—")
    industry = company_info.get("industry", "—")
    currency = company_info.get("currency", "USD")
    mcap = company_info.get("market_cap")
    mcap_str = f"{mcap/1e9:.1f}B {currency}" if mcap else "—"

    # 渲染所有图表为 base64
    chart_html_blocks = {}
    for chart in charts:
        b64 = fig_to_png_base64(chart["fig"])
        if b64:
            chart_html_blocks[chart["id"]] = f"""
            <div class="chart-block">
                <img src="data:image/png;base64,{b64}" alt="{chart['title']}" />
                <div class="chart-caption">图: {chart['title']}</div>
            </div>"""
        else:
            chart_html_blocks[chart["id"]] = (
                f'<p class="chart-caption">⚠️ 图表「{chart["title"]}」无法渲染'
                f'(服务器缺少 kaleido 库)</p>'
            )

    # LLM 分析转 HTML
    analysis_html = md_to_html(llm_analysis)

    # 把图表插入到合适章节
    # 策略:在 LLM 分析后,按章节追加图表
    charts_by_category = {}
    for ch in charts:
        cat = ch["category"]
        charts_by_category.setdefault(cat, []).append(ch)

    # 生成数据表 HTML(关键比率表)
    ratios_table_html = "<table><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>"
    for k, v in ratios.items():
        if k.startswith("_"):
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
        ratios_table_html += f"<tr><td>{k}</td><td>{disp}</td></tr>"
    ratios_table_html += "</tbody></table>"

    # 同行对比表
    peer_table_html = ""
    if not compare_df.empty:
        peer_table_html = "<h3>同行业数据对照表</h3><table><thead><tr><th>指标</th>"
        for col in compare_df.columns:
            peer_table_html += f"<th>{col}</th>"
        peer_table_html += "</tr></thead><tbody>"
        for idx in compare_df.index:
            is_pct = (any(kw in idx for kw in ["ROE", "ROA", "Margin"]) or
                      ("率" in idx and not any(x in idx for x in ["流动比率", "速动比率", "周转率"])))
            peer_table_html += f"<tr><td>{idx}</td>"
            for col in compare_df.columns:
                v = compare_df.loc[idx, col]
                if pd.isna(v):
                    disp = "—"
                elif is_pct:
                    disp = f"{v*100:.2f}%"
                else:
                    disp = f"{v:.3f}"
                peer_table_html += f"<td>{disp}</td>"
            peer_table_html += "</tr>"
        peer_table_html += "</tbody></table>"

    # 拼接图表节
    charts_section = ""
    for cat, chs in charts_by_category.items():
        charts_section += f"<h2>📊 {cat}</h2>\n"
        for ch in chs:
            charts_section += chart_html_blocks.get(ch["id"], "")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{name} ({ticker}) {year} 年财务分析报告</title>
{HTML_CSS}
</head>
<body>

<h1>{name} ({ticker})</h1>
<p class="meta">
<strong>{year} 年度财务分析报告</strong><br>
行业: {sector} / {industry} &nbsp;|&nbsp; 国家: {company_info.get('country', '—')} \
&nbsp;|&nbsp; 市值: {mcap_str}
</p>

<div class="summary-box">
本报告由 AI 财务分析 Agent 自动生成,综合杜邦分析、趋势分析、同行业比较和基准评级,\
并由大语言模型撰写深度解读。
</div>

<h2>📋 关键比率一览</h2>
{ratios_table_html}

{peer_table_html}

<h2>🤖 AI 深度分析</h2>
{analysis_html}

{charts_section}

<div class="footer">
本报告基于 Yahoo Finance 公开财务数据自动生成,仅供学术与参考用途,不构成投资建议。<br>
Generated by Financial Analysis AI Agent.
</div>

</body>
</html>"""


# ============================================================
# DOCX 报告
# ============================================================
def build_docx_report(company_info: Dict, year: int, llm_analysis: str,
                       charts: List[Dict], ratios: Dict,
                       compare_df: pd.DataFrame) -> bytes:
    """构建 Word 报告 → bytes"""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # 标题
    title = doc.add_heading(
        f"{company_info.get('name', '')} ({company_info.get('ticker', '')})", level=0)
    subtitle = doc.add_paragraph(f"{year} 年度财务分析报告")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 元信息
    meta_p = doc.add_paragraph()
    meta_p.add_run(f"行业: {company_info.get('sector', '—')} / "
                    f"{company_info.get('industry', '—')}\n").italic = True
    meta_p.add_run(f"国家: {company_info.get('country', '—')}  |  ").italic = True
    mcap = company_info.get("market_cap")
    mcap_str = f"{mcap/1e9:.1f}B {company_info.get('currency', 'USD')}" if mcap else "—"
    meta_p.add_run(f"市值: {mcap_str}").italic = True

    doc.add_paragraph(
        "本报告由 AI 财务分析 Agent 自动生成,综合多种分析方法并由 LLM 撰写深度解读。"
    )

    # 关键比率表
    doc.add_heading("📋 关键比率一览", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "指标"
    hdr[1].text = "数值"
    for k, v in ratios.items():
        if k.startswith("_"):
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
        row = table.add_row().cells
        row[0].text = k
        row[1].text = disp

    # 同行表
    if not compare_df.empty:
        doc.add_heading("同行业对照", level=2)
        peer_table = doc.add_table(rows=1, cols=len(compare_df.columns) + 1)
        peer_table.style = "Light Grid Accent 1"
        hdr = peer_table.rows[0].cells
        hdr[0].text = "指标"
        for i, col in enumerate(compare_df.columns):
            hdr[i + 1].text = str(col)[:25]
        for idx in compare_df.index:
            is_pct = (any(kw in idx for kw in ["ROE", "ROA", "Margin"]) or
                      ("率" in idx and not any(x in idx for x in ["流动比率", "速动比率", "周转率"])))
            row = peer_table.add_row().cells
            row[0].text = idx
            for i, col in enumerate(compare_df.columns):
                v = compare_df.loc[idx, col]
                if pd.isna(v):
                    row[i + 1].text = "—"
                elif is_pct:
                    row[i + 1].text = f"{v*100:.2f}%"
                else:
                    row[i + 1].text = f"{v:.3f}"

    # AI 分析(渲染 Markdown 简化版)
    doc.add_heading("🤖 AI 深度分析", level=1)
    for line in llm_analysis.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("- ") or line.startswith("* "):
            p = doc.add_paragraph(style="List Bullet")
            _add_runs_with_bold(p, line[2:])
        else:
            p = doc.add_paragraph()
            _add_runs_with_bold(p, line)

    # 插入图表
    charts_by_cat = {}
    for ch in charts:
        charts_by_cat.setdefault(ch["category"], []).append(ch)

    for cat, chs in charts_by_cat.items():
        doc.add_heading(f"📊 {cat}", level=1)
        for ch in chs:
            png = fig_to_png_bytes(ch["fig"])
            if png:
                doc.add_picture(io.BytesIO(png), width=Inches(6.0))
                caption = doc.add_paragraph(f"图: {ch['title']}")
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in caption.runs:
                    run.italic = True
                    run.font.size = Pt(9)
            else:
                p = doc.add_paragraph(f"⚠️ 图表「{ch['title']}」无法渲染")
                p.italic = True

    # 保存
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_runs_with_bold(paragraph, text):
    """处理 **粗体** 渲染到 docx"""
    import re
    parts = re.split(r"(\*\*[^\*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)


# ============================================================
# PDF 报告 - 通过 HTML 转换
# ============================================================
def build_pdf_report(html_content: str) -> Optional[bytes]:
    """
    HTML → PDF。使用 weasyprint(若可用)或 fpdf 兜底。
    Streamlit Cloud 默认不带 weasyprint 的系统依赖,所以可能失败。
    失败时返回 None,前端应回退提示用户用 HTML/DOCX。
    """
    # 方案 1:weasyprint(最佳质量,需系统库)
    try:
        from weasyprint import HTML
        return HTML(string=html_content).write_pdf()
    except Exception:
        pass

    # 方案 2:无可用工具
    return None
