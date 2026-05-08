"""
AI Agent 可调用的工具集
每个工具都是一个 Python 函数 + JSON Schema 描述
"""
import pandas as pd
from typing import Dict, List, Optional
from utils.data_fetcher import (
    fetch_company_info, fetch_financials, search_ticker_by_name, looks_like_ticker,
    get_peer_suggestions_by_size
)
from utils.ratios import compute_ratios_for_year, compute_multi_year_ratios, dupont_analysis
from utils.benchmark import compare_with_peers, benchmark_analysis, evaluate_against_benchmark
from utils.report import generate_report


# ============================================================
# 内部辅助:把公司名/ticker 解析成 ticker
# ============================================================
def resolve_ticker(company: str) -> Optional[str]:
    """把公司名或 ticker 解析成标准 ticker"""
    if not company:
        return None
    company = company.strip()
    if looks_like_ticker(company):
        return company.upper()
    matches = search_ticker_by_name(company)
    return matches[0]["ticker"] if matches else None


def get_year_col(income_df: pd.DataFrame, target_year: int):
    """找到 <= target_year 的最近一年"""
    if income_df.empty:
        return None, None
    cols = sorted(income_df.columns, reverse=True)
    cols_filtered = [c for c in cols if c.year <= target_year]
    if not cols_filtered:
        return None, None
    year_col = cols_filtered[0]
    prev_col = cols_filtered[1] if len(cols_filtered) > 1 else None
    return year_col, prev_col


# ============================================================
# 工具实现
# ============================================================

def tool_fetch_company(company: str) -> Dict:
    """获取公司基本信息"""
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」对应的股票代码"}
    info = fetch_company_info(ticker)
    if "error" in info:
        return {"error": f"获取数据失败: {info.get('error')}"}
    return {
        "ticker": info["ticker"],
        "name": info.get("name"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "currency": info.get("currency"),
        "market_cap": info.get("market_cap"),
        "summary": (info.get("summary") or "")[:500],
    }


def tool_compute_ratios(company: str, year: int = 2024) -> Dict:
    """计算指定公司、指定年份的财务比率"""
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」"}

    fin = fetch_financials(ticker)
    income = fin.get("income", pd.DataFrame())
    balance = fin.get("balance", pd.DataFrame())
    cashflow = fin.get("cashflow", pd.DataFrame())

    if income.empty:
        return {"error": f"{ticker} 财报数据不可用"}

    year_col, prev_col = get_year_col(income, year)
    if year_col is None:
        return {"error": f"未找到 {year} 年或更早的财报"}

    ratios = compute_ratios_for_year(income, balance, cashflow, year_col, prev_col)
    # 过滤内部字段并附上评级
    result = {"ticker": ticker, "actual_year": year_col.year, "ratios": {}}
    for k, v in ratios.items():
        if k.startswith("_"):
            continue
        rating = evaluate_against_benchmark(k, v) if v is not None else "—"
        result["ratios"][k] = {
            "value": round(v, 4) if v is not None else None,
            "rating": rating,
        }
    return result


def tool_dupont_analysis(company: str, year: int = 2024) -> Dict:
    """杜邦分析:ROE 三因素分解"""
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」"}

    fin = fetch_financials(ticker)
    income = fin.get("income", pd.DataFrame())
    balance = fin.get("balance", pd.DataFrame())
    cashflow = fin.get("cashflow", pd.DataFrame())
    if income.empty:
        return {"error": f"{ticker} 财报数据不可用"}

    year_col, prev_col = get_year_col(income, year)
    if year_col is None:
        return {"error": f"未找到 {year} 年财报"}

    ratios = compute_ratios_for_year(income, balance, cashflow, year_col, prev_col)
    dp = dupont_analysis(ratios)

    calc_method = ratios.get("_calc_method", "ending")
    method_note = (
        "本结果使用「平均权益」(期初+期末)/2 计算,符合标准财务分析口径"
        if calc_method == "average"
        else "⚠️ 本结果使用「期末权益」计算(因 yfinance 缺少前一年数据"
              ",通常仅近 4 年有完整可比数据)。该结果会偏离用'平均权益'的标准口径,"
              "尤其对回购密集的公司差异显著(如 Apple 因股票回购导致期末权益低,ROE 显著偏高)"
    )

    return {
        "ticker": ticker,
        "year": year_col.year,
        "净利率 (Net Margin)": round(dp["净利率"], 4) if dp["净利率"] else None,
        "总资产周转率 (Asset Turnover)": round(dp["总资产周转率"], 4) if dp["总资产周转率"] else None,
        "权益乘数 (Equity Multiplier)": round(dp["权益乘数"], 4) if dp["权益乘数"] else None,
        "ROE (杜邦计算)": round(dp["ROE (杜邦计算)"], 4) if dp["ROE (杜邦计算)"] else None,
        "ROE (直接计算)": round(dp["ROE (直接计算)"], 4) if dp["ROE (直接计算)"] else None,
        "计算方法": calc_method,
        "计算方法说明": method_note,
        "解读": "ROE = 净利率 × 总资产周转率 × 权益乘数。三个因素分别反映销售盈利、资产效率、财务杠杆。"
    }


def tool_trend_analysis(company: str, num_years: int = 5,
                          target_year: int = 2024) -> Dict:
    """趋势分析:多年度核心指标变化"""
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」"}

    fin = fetch_financials(ticker)
    if fin.get("income", pd.DataFrame()).empty:
        return {"error": f"{ticker} 财报数据不可用"}

    trend_df = compute_multi_year_ratios(fin, target_year, num_years=num_years)
    if trend_df.empty:
        return {"error": "趋势数据不足"}

    # 关键指标的趋势
    key_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率", "ROA 总资产收益率",
                   "毛利率 (Gross Margin)", "资产负债率", "总资产周转率"]
    result = {"ticker": ticker, "years": [int(y) for y in trend_df.columns],
              "actual_years_count": len(trend_df.columns), "trends": {}}

    for m in key_metrics:
        if m not in trend_df.index:
            continue
        series = trend_df.loc[m]
        values = [round(v, 4) if pd.notna(v) else None for v in series.values]
        result["trends"][m] = values

    # 趋势方向
    direction = {}
    for m, values in result["trends"].items():
        clean = [v for v in values if v is not None]
        if len(clean) >= 2:
            change = (clean[-1] - clean[0]) / abs(clean[0]) if clean[0] != 0 else 0
            if change > 0.1:
                direction[m] = "明显上升"
            elif change > 0.02:
                direction[m] = "小幅上升"
            elif change < -0.1:
                direction[m] = "明显下降"
            elif change < -0.02:
                direction[m] = "小幅下降"
            else:
                direction[m] = "基本持平"
    result["direction"] = direction
    return result


def tool_peer_comparison(company: str, peers: Optional[List[str]] = None,
                          year: int = 2024, auto_match: bool = False) -> Dict:
    """
    同行业比较
    - peers: 用户指定的同行公司名/ticker 列表
    - auto_match: 如果 True 或 peers 为空,自动按行业+规模匹配
    """
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」"}

    info = fetch_company_info(ticker)

    # 解析同行
    peer_tickers = []
    if peers:
        for p in peers:
            t = resolve_ticker(p)
            if t and t != ticker:
                peer_tickers.append(t)

    if not peer_tickers and (auto_match or not peers):
        suggestions = get_peer_suggestions_by_size(
            sector=info.get("sector", ""),
            target_market_cap=info.get("market_cap"),
            exclude=ticker, n=4,
            company_name=info.get("name", ""),
            industry=info.get("industry", ""),
            country=info.get("country", ""),
        )
        peer_tickers = [s["ticker"] for s in suggestions]

    if not peer_tickers:
        return {"error": "未能找到合适的同行公司"}

    compare_df = compare_with_peers(ticker, peer_tickers, year)
    if compare_df.empty:
        return {"error": "同行数据获取失败"}

    # 关键指标对比
    key_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率", "ROA 总资产收益率",
                   "毛利率 (Gross Margin)", "资产负债率"]
    result = {
        "ticker": ticker,
        "year": year,
        "peers_used": peer_tickers,
        "comparison": {},
    }
    for m in key_metrics:
        if m not in compare_df.index:
            continue
        row = compare_df.loc[m]
        result["comparison"][m] = {
            col: round(v, 4) if pd.notna(v) else None
            for col, v in row.items()
        }
    return result


def tool_generate_full_report(company: str, year: int = 2024,
                                include_peers: bool = True) -> Dict:
    """生成完整 Markdown 分析报告

    返回的 dict 包含给 LLM 看的元数据 + 给 UI 渲染下载按钮用的完整数据。
    chat_page 会用 _full_data 字段调用 build_html/docx/pdf_report 输出 4 种格式,
    与经典模式完全一致。
    """
    ticker = resolve_ticker(company)
    if not ticker:
        return {"error": f"无法找到公司「{company}」"}

    info = fetch_company_info(ticker)
    fin = fetch_financials(ticker)
    income = fin.get("income", pd.DataFrame())
    balance = fin.get("balance", pd.DataFrame())
    cashflow = fin.get("cashflow", pd.DataFrame())

    if income.empty:
        return {"error": "财报数据不可用"}

    year_col, prev_col = get_year_col(income, year)
    if year_col is None:
        return {"error": f"未找到 {year} 年财报"}

    ratios = compute_ratios_for_year(income, balance, cashflow, year_col, prev_col)
    dp = dupont_analysis(ratios)
    trend_df = compute_multi_year_ratios(fin, year, num_years=5)

    # 同行
    compare_df = pd.DataFrame()
    if include_peers:
        suggestions = get_peer_suggestions_by_size(
            sector=info.get("sector", ""),
            target_market_cap=info.get("market_cap"),
            exclude=ticker, n=3,
            company_name=info.get("name", ""),
            industry=info.get("industry", ""),
            country=info.get("country", ""),
        )
        peer_tickers = [s["ticker"] for s in suggestions]
        if peer_tickers:
            compare_df = compare_with_peers(ticker, peer_tickers, year)

    actual_year = year_col.year

    # 简版 Markdown(快速兜底,如果 AI 章节生成失败时用)
    md = generate_report(info, ratios, dp, trend_df, compare_df, actual_year)

    return {
        "ticker": ticker,
        "year": actual_year,
        "report_markdown": md,
        "filename": f"{ticker}_{actual_year}_财务分析报告.md",
        # ★ 完整数据(给 UI 用,LLM 不会看到这部分)
        "_full_data": {
            "info": info,
            "ratios": ratios,
            "dupont": dp,
            "trend_df": trend_df,
            "compare_df": compare_df,
            "actual_year": actual_year,
            "ticker": ticker,
        },
    }


# ============================================================
# 工具的 JSON Schema 定义(给 OpenAI Function Calling 用)
# ============================================================
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_company",
            "description": "获取公司基本信息(行业、市值、简介等)。用户提到任何公司时都应先调用此工具确认存在。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名或股票代码,如「苹果」、「Apple」、「AAPL」、「腾讯」、「0700.HK」"
                    }
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_ratios",
            "description": "计算指定公司、指定年份的全部财务比率(盈利、运营、偿债、现金流)。返回每个比率的值和评级。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "公司名或代码"},
                    "year": {"type": "integer", "description": "目标财年,默认 2024"},
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dupont_analysis",
            "description": "杜邦分析:把 ROE 分解为「净利率 × 总资产周转率 × 权益乘数」三个因素,识别盈利能力的核心驱动力。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "公司名或代码"},
                    "year": {"type": "integer", "description": "目标财年,默认 2024"},
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trend_analysis",
            "description": "多年度趋势分析,展示核心指标在过去几年的变化方向(上升/下降/持平)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "公司名或代码"},
                    "num_years": {"type": "integer", "description": "回溯年数,默认 5(实际可能更少)"},
                    "target_year": {"type": "integer", "description": "终点年份,默认 2024"},
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "peer_comparison",
            "description": "同行业比较。用户没指定同行时设 auto_match=true,会按行业+规模自动匹配。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "目标公司"},
                    "peers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "用户指定的同行公司名/代码列表,可空"
                    },
                    "year": {"type": "integer", "description": "财年,默认 2024"},
                    "auto_match": {
                        "type": "boolean",
                        "description": "未指定同行时是否自动按行业+规模匹配,默认 true",
                        "default": True,
                    },
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_full_report",
            "description": "生成完整的 Markdown 财务分析报告,涵盖比率、杜邦、趋势、同行、基准、综合评价。当用户要求「完整报告」「全面分析」「下载报告」时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "year": {"type": "integer", "description": "默认 2024"},
                    "include_peers": {"type": "boolean", "default": True},
                },
                "required": ["company"],
            },
        },
    },
]


# ============================================================
# 工具分发器
# ============================================================
TOOL_FUNCTIONS = {
    "fetch_company": tool_fetch_company,
    "compute_ratios": tool_compute_ratios,
    "dupont_analysis": tool_dupont_analysis,
    "trend_analysis": tool_trend_analysis,
    "peer_comparison": tool_peer_comparison,
    "generate_full_report": tool_generate_full_report,
}


def execute_tool(name: str, args: Dict) -> Dict:
    """根据 LLM 返回的工具名+参数,执行工具并返回结果"""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return {"error": f"未知工具: {name}"}
    try:
        return func(**args)
    except Exception as e:
        return {"error": f"工具执行失败: {type(e).__name__}: {str(e)}"}
