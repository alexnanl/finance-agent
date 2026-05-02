"""
财务比率计算模块
覆盖盈利能力、运营能力、偿债能力、成长能力 + 杜邦分析
"""
import pandas as pd
from typing import Dict, Optional, List


def get_value(df: pd.DataFrame, candidates: List[str], col) -> Optional[float]:
    """在 DataFrame 中按候选名查找指标值。yfinance 字段名不同公司可能略有差异。"""
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            try:
                val = df.loc[name, col]
                if pd.isna(val):
                    continue
                return float(val)
            except (KeyError, ValueError, TypeError):
                continue
    return None


# 字段候选名 - yfinance 不同公司字段命名可能略有差异
FIELDS = {
    "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
    "cogs": ["Cost Of Revenue", "Cost of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "ebit": ["EBIT", "Operating Income"],
    "net_income": ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "tax_expense": ["Tax Provision", "Income Tax Expense"],
    "pretax_income": ["Pretax Income", "Income Before Tax"],

    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets", "Total Current Assets"],
    "current_liab": ["Current Liabilities", "Total Current Liabilities"],
    "total_liab": ["Total Liabilities Net Minority Interest", "Total Liab"],
    "total_equity": ["Total Equity Gross Minority Interest", "Stockholders Equity",
                     "Common Stock Equity", "Total Stockholder Equity"],
    "cash": ["Cash And Cash Equivalents", "Cash"],
    "inventory": ["Inventory"],
    "receivables": ["Accounts Receivable", "Receivables"],
    "payables": ["Accounts Payable", "Payables"],
    "long_term_debt": ["Long Term Debt"],
    "short_term_debt": ["Short Term Debt", "Current Debt"],

    "operating_cf": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure"],
    "free_cf": ["Free Cash Flow"],
}


def safe_div(a, b) -> Optional[float]:
    """安全除法,避免分母为零或 None"""
    if a is None or b is None:
        return None
    try:
        if b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError):
        return None


def avg(a, b) -> Optional[float]:
    """两期平均(用于资产周转率等指标),只有一期数据时返回该期"""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2


def compute_ratios_for_year(income_df: pd.DataFrame, balance_df: pd.DataFrame,
                              cashflow_df: pd.DataFrame, year_col, prev_year_col=None) -> Dict:
    """
    计算单一年度的全部比率
    year_col: 当期列名(timestamp)
    prev_year_col: 上期列名,用于计算需要平均值的指标
    """
    g = lambda df, key, col: get_value(df, FIELDS[key], col)

    # 利润表项
    revenue = g(income_df, "revenue", year_col)
    cogs = g(income_df, "cogs", year_col)
    gross_profit = g(income_df, "gross_profit", year_col)
    if gross_profit is None and revenue is not None and cogs is not None:
        gross_profit = revenue - cogs
    op_income = g(income_df, "operating_income", year_col)
    net_income = g(income_df, "net_income", year_col)
    interest = g(income_df, "interest_expense", year_col)
    tax = g(income_df, "tax_expense", year_col)
    pretax = g(income_df, "pretax_income", year_col)

    # 资产负债表项 - 当期
    assets = g(balance_df, "total_assets", year_col)
    cur_assets = g(balance_df, "current_assets", year_col)
    cur_liab = g(balance_df, "current_liab", year_col)
    total_liab = g(balance_df, "total_liab", year_col)
    equity = g(balance_df, "total_equity", year_col)
    inventory = g(balance_df, "inventory", year_col)
    receivables = g(balance_df, "receivables", year_col)
    cash = g(balance_df, "cash", year_col)
    lt_debt = g(balance_df, "long_term_debt", year_col)
    st_debt = g(balance_df, "short_term_debt", year_col)

    # 上期(用于平均)
    if prev_year_col is not None:
        prev_assets = g(balance_df, "total_assets", prev_year_col)
        prev_equity = g(balance_df, "total_equity", prev_year_col)
        prev_inventory = g(balance_df, "inventory", prev_year_col)
        prev_receivables = g(balance_df, "receivables", prev_year_col)
    else:
        prev_assets = prev_equity = prev_inventory = prev_receivables = None

    avg_assets = avg(assets, prev_assets) if prev_assets else assets
    avg_equity = avg(equity, prev_equity) if prev_equity else equity
    avg_inventory = avg(inventory, prev_inventory) if prev_inventory else inventory
    avg_receivables = avg(receivables, prev_receivables) if prev_receivables else receivables

    # 现金流
    op_cf = get_value(cashflow_df, FIELDS["operating_cf"], year_col)
    capex = get_value(cashflow_df, FIELDS["capex"], year_col)
    fcf = get_value(cashflow_df, FIELDS["free_cf"], year_col)
    if fcf is None and op_cf is not None and capex is not None:
        fcf = op_cf + capex  # capex 一般为负

    # 计算总债务
    total_debt = None
    if lt_debt is not None or st_debt is not None:
        total_debt = (lt_debt or 0) + (st_debt or 0)

    ratios = {
        # ===== 盈利能力 =====
        "毛利率 (Gross Margin)": safe_div(gross_profit, revenue),
        "营业利润率 (Operating Margin)": safe_div(op_income, revenue),
        "净利率 (Net Margin)": safe_div(net_income, revenue),
        "ROA 总资产收益率": safe_div(net_income, avg_assets),
        "ROE 净资产收益率": safe_div(net_income, avg_equity),
        "ROIC 投入资本回报率": safe_div(
            (op_income * (1 - safe_div(tax, pretax) or 0.21)) if op_income else None,
            (equity or 0) + (total_debt or 0) if (equity or total_debt) else None
        ) if op_income and (equity or total_debt) else None,

        # ===== 运营能力 =====
        "总资产周转率": safe_div(revenue, avg_assets),
        "存货周转率": safe_div(cogs, avg_inventory),
        "应收账款周转率": safe_div(revenue, avg_receivables),

        # ===== 偿债能力 =====
        "流动比率": safe_div(cur_assets, cur_liab),
        "速动比率": safe_div(
            (cur_assets - inventory) if (cur_assets is not None and inventory is not None) else cur_assets,
            cur_liab
        ),
        "资产负债率": safe_div(total_liab, assets),
        "权益乘数 (Equity Multiplier)": safe_div(avg_assets, avg_equity),
        "利息保障倍数": safe_div(op_income, abs(interest)) if interest else None,

        # ===== 现金流 =====
        "经营现金流/收入": safe_div(op_cf, revenue),
        "自由现金流 (FCF, 原币)": fcf,

        # ===== 原始值(供报告使用) =====
        "_revenue": revenue,
        "_net_income": net_income,
        "_total_assets": assets,
        "_equity": equity,
    }
    return ratios


def dupont_analysis(ratios: Dict) -> Dict:
    """
    杜邦分析:
    ROE = 净利率 × 总资产周转率 × 权益乘数
    """
    nm = ratios.get("净利率 (Net Margin)")
    ato = ratios.get("总资产周转率")
    em = ratios.get("权益乘数 (Equity Multiplier)")
    roe_calc = nm * ato * em if (nm is not None and ato is not None and em is not None) else None

    return {
        "净利率": nm,
        "总资产周转率": ato,
        "权益乘数": em,
        "ROE (杜邦计算)": roe_calc,
        "ROE (直接计算)": ratios.get("ROE 净资产收益率"),
    }


def compute_multi_year_ratios(financials: Dict[str, pd.DataFrame], target_year: int,
                                num_years: int = 5) -> pd.DataFrame:
    """
    计算多年度比率,用于趋势分析
    返回 DataFrame: 行=指标,列=年份
    """
    income_df = financials.get("income", pd.DataFrame())
    balance_df = financials.get("balance", pd.DataFrame())
    cashflow_df = financials.get("cashflow", pd.DataFrame())

    if income_df.empty:
        return pd.DataFrame()

    # 取所有可用年份(yfinance 列是 timestamp,降序)
    cols = sorted(income_df.columns, reverse=True)

    # 筛选出 <= target_year 的列
    cols = [c for c in cols if c.year <= target_year][:num_years]
    cols = sorted(cols)  # 升序方便趋势图

    result = {}
    for i, col in enumerate(cols):
        prev_col = cols[i - 1] if i > 0 else None
        ratios = compute_ratios_for_year(income_df, balance_df, cashflow_df, col, prev_col)
        result[col.year] = ratios

    df = pd.DataFrame(result)
    # 过滤内部字段(下划线开头)
    df = df[~df.index.str.startswith("_")]
    return df
