"""
同行业比较 + 基准分析
"""
import pandas as pd
from typing import List, Dict
from utils.ratios import compute_ratios_for_year


# 行业经验基准值(粗略,供参考)
# 来源:综合各行业研究的常见经验阈值
GENERIC_BENCHMARKS = {
    "毛利率 (Gross Margin)": {"优秀": 0.40, "良好": 0.25, "一般": 0.15},
    "营业利润率 (Operating Margin)": {"优秀": 0.20, "良好": 0.10, "一般": 0.05},
    "净利率 (Net Margin)": {"优秀": 0.15, "良好": 0.08, "一般": 0.03},
    "ROA 总资产收益率": {"优秀": 0.10, "良好": 0.05, "一般": 0.02},
    "ROE 净资产收益率": {"优秀": 0.20, "良好": 0.12, "一般": 0.06},
    "流动比率": {"优秀": 2.0, "良好": 1.5, "一般": 1.0},
    "速动比率": {"优秀": 1.5, "良好": 1.0, "一般": 0.7},
    "资产负债率": {"优秀": 0.40, "良好": 0.60, "一般": 0.75},  # 越低越好
    "总资产周转率": {"优秀": 1.0, "良好": 0.6, "一般": 0.3},
    "利息保障倍数": {"优秀": 8.0, "良好": 4.0, "一般": 2.0},
}

# 哪些指标"越低越好"
LOWER_IS_BETTER = {"资产负债率"}


def evaluate_against_benchmark(ratio_name: str, value: float) -> str:
    """根据通用基准给出评级"""
    if value is None or ratio_name not in GENERIC_BENCHMARKS:
        return "—"
    bm = GENERIC_BENCHMARKS[ratio_name]
    lower_better = ratio_name in LOWER_IS_BETTER

    if lower_better:
        if value <= bm["优秀"]:
            return "🟢 优秀"
        elif value <= bm["良好"]:
            return "🟡 良好"
        elif value <= bm["一般"]:
            return "🟠 一般"
        else:
            return "🔴 偏弱"
    else:
        if value >= bm["优秀"]:
            return "🟢 优秀"
        elif value >= bm["良好"]:
            return "🟡 良好"
        elif value >= bm["一般"]:
            return "🟠 一般"
        else:
            return "🔴 偏弱"


def compare_with_peers(target_ticker: str, peer_tickers: List[str],
                        target_year: int) -> pd.DataFrame:
    """
    同行业对比
    返回 DataFrame: 行=指标,列=公司
    """
    # 延迟导入,避免离线测试时引入 yfinance
    from utils.data_fetcher import fetch_company_info, fetch_financials

    all_tickers = [target_ticker] + peer_tickers
    result = {}

    for tk in all_tickers:
        try:
            financials = fetch_financials(tk)
            income_df = financials.get("income", pd.DataFrame())
            balance_df = financials.get("balance", pd.DataFrame())
            cashflow_df = financials.get("cashflow", pd.DataFrame())

            if income_df.empty:
                continue

            # 找到 <= target_year 的最近列
            cols = sorted(income_df.columns, reverse=True)
            cols = [c for c in cols if c.year <= target_year]
            if not cols:
                continue
            year_col = cols[0]
            prev_col = cols[1] if len(cols) > 1 else None

            ratios = compute_ratios_for_year(income_df, balance_df, cashflow_df,
                                              year_col, prev_col)
            # 用 ticker 作为列名
            info = fetch_company_info(tk)
            display_name = f"{tk} ({info.get('name', tk)[:20]})"
            result[display_name] = ratios
        except Exception:
            continue

    df = pd.DataFrame(result)
    df = df[~df.index.str.startswith("_")]
    return df


def benchmark_analysis(ratios_dict: Dict) -> pd.DataFrame:
    """生成基准对比表"""
    rows = []
    for ratio_name, value in ratios_dict.items():
        if ratio_name.startswith("_"):
            continue
        if ratio_name not in GENERIC_BENCHMARKS:
            continue
        bm = GENERIC_BENCHMARKS[ratio_name]
        rows.append({
            "指标": ratio_name,
            "公司值": value,
            "优秀基准": bm["优秀"],
            "良好基准": bm["良好"],
            "一般基准": bm["一般"],
            "评级": evaluate_against_benchmark(ratio_name, value),
        })
    return pd.DataFrame(rows)
