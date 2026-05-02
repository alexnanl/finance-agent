"""
中文分析报告生成
基于规则的智能解读 + 可选的 LLM 增强
"""
import pandas as pd
from typing import Dict, List
from utils.benchmark import GENERIC_BENCHMARKS, LOWER_IS_BETTER, evaluate_against_benchmark


def fmt_pct(v):
    if v is None or pd.isna(v):
        return "N/A"
    return f"{v * 100:.2f}%"


def fmt_num(v, decimals=2):
    if v is None or pd.isna(v):
        return "N/A"
    return f"{v:.{decimals}f}"


def trend_direction(series: pd.Series) -> str:
    """判断趋势方向"""
    s = series.dropna()
    if len(s) < 2:
        return "数据不足"
    first, last = s.iloc[0], s.iloc[-1]
    if first == 0:
        return "持平"
    change = (last - first) / abs(first)
    if change > 0.10:
        return f"明显上升(累计 +{change*100:.1f}%)"
    elif change > 0.02:
        return f"小幅上升(+{change*100:.1f}%)"
    elif change < -0.10:
        return f"明显下降({change*100:.1f}%)"
    elif change < -0.02:
        return f"小幅下降({change*100:.1f}%)"
    else:
        return "基本持平"


def generate_report(company_info: Dict, ratios: Dict, dupont: Dict,
                    trend_df: pd.DataFrame, compare_df: pd.DataFrame,
                    target_year: int) -> str:
    """生成完整中文分析报告(Markdown 格式)"""

    name = company_info.get("name", "公司")
    ticker = company_info.get("ticker", "")
    sector = company_info.get("sector", "N/A")
    industry = company_info.get("industry", "N/A")
    currency = company_info.get("currency", "USD")

    md = []
    md.append(f"# {name} ({ticker}) — {target_year} 年度财务分析报告\n")
    md.append(f"**所属行业**: {sector} / {industry}  ")
    md.append(f"**财报币种**: {currency}\n")
    md.append("---\n")

    # ===== 1. 摘要 =====
    md.append("## 一、核心摘要\n")
    roe = ratios.get("ROE 净资产收益率")
    nm = ratios.get("净利率 (Net Margin)")
    da = ratios.get("资产负债率")
    cr = ratios.get("流动比率")

    summary_points = []
    if roe is not None:
        rating = evaluate_against_benchmark("ROE 净资产收益率", roe)
        summary_points.append(f"- **盈利能力**: ROE = {fmt_pct(roe)},评级 {rating}")
    if nm is not None:
        rating = evaluate_against_benchmark("净利率 (Net Margin)", nm)
        summary_points.append(f"- **净利率**: {fmt_pct(nm)},评级 {rating}")
    if da is not None:
        rating = evaluate_against_benchmark("资产负债率", da)
        summary_points.append(f"- **杠杆水平**: 资产负债率 = {fmt_pct(da)},评级 {rating}")
    if cr is not None:
        rating = evaluate_against_benchmark("流动比率", cr)
        summary_points.append(f"- **短期偿债**: 流动比率 = {fmt_num(cr)},评级 {rating}")

    md.append("\n".join(summary_points))
    md.append("\n")

    # ===== 2. 比率分析 =====
    md.append("\n## 二、比率分析\n")
    md.append("### 2.1 盈利能力\n")
    md.append(f"- 毛利率: **{fmt_pct(ratios.get('毛利率 (Gross Margin)'))}**  ")
    md.append(f"- 营业利润率: **{fmt_pct(ratios.get('营业利润率 (Operating Margin)'))}**  ")
    md.append(f"- 净利率: **{fmt_pct(nm)}**  ")
    md.append(f"- ROA: **{fmt_pct(ratios.get('ROA 总资产收益率'))}**  ")
    md.append(f"- ROE: **{fmt_pct(roe)}**  \n")

    md.append("### 2.2 运营能力\n")
    md.append(f"- 总资产周转率: **{fmt_num(ratios.get('总资产周转率'))} 次**  ")
    md.append(f"- 存货周转率: **{fmt_num(ratios.get('存货周转率'))} 次**  ")
    md.append(f"- 应收账款周转率: **{fmt_num(ratios.get('应收账款周转率'))} 次**  \n")

    md.append("### 2.3 偿债能力\n")
    md.append(f"- 流动比率: **{fmt_num(cr)}**  ")
    md.append(f"- 速动比率: **{fmt_num(ratios.get('速动比率'))}**  ")
    md.append(f"- 资产负债率: **{fmt_pct(da)}**  ")
    md.append(f"- 利息保障倍数: **{fmt_num(ratios.get('利息保障倍数'))}** 倍  \n")

    # ===== 3. 杜邦分析 =====
    md.append("\n## 三、杜邦分析\n")
    md.append("> **ROE = 净利率 × 总资产周转率 × 权益乘数**\n")
    md.append(f"- 净利率(销售盈利): **{fmt_pct(dupont.get('净利率'))}**  ")
    md.append(f"- 总资产周转率(资产运营效率): **{fmt_num(dupont.get('总资产周转率'))}**  ")
    md.append(f"- 权益乘数(财务杠杆): **{fmt_num(dupont.get('权益乘数'))}**  ")
    md.append(f"- **杜邦计算 ROE**: {fmt_pct(dupont.get('ROE (杜邦计算)'))}  ")
    md.append(f"- **直接计算 ROE**: {fmt_pct(dupont.get('ROE (直接计算)'))}  \n")

    # 杜邦解读
    nm_v = dupont.get("净利率") or 0
    ato_v = dupont.get("总资产周转率") or 0
    em_v = dupont.get("权益乘数") or 0
    factors = [("净利率", nm_v, 0.10), ("总资产周转率", ato_v, 0.6), ("权益乘数", em_v, 2.0)]
    drivers = []
    for fname, val, threshold in factors:
        if val > threshold * 1.2:
            drivers.append(f"{fname}较高({fmt_num(val) if fname != '净利率' else fmt_pct(val)})")

    if drivers:
        md.append(f"**ROE 主要驱动因素**: {','.join(drivers)}。")
    md.append("")

    # ===== 4. 趋势分析 =====
    md.append("\n## 四、趋势分析\n")
    if trend_df is not None and not trend_df.empty:
        years_str = " → ".join(str(c) for c in trend_df.columns)
        md.append(f"覆盖年度: {years_str}\n")

        key_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率", "ROA 总资产收益率",
                       "资产负债率", "流动比率", "总资产周转率"]
        for m in key_metrics:
            if m in trend_df.index:
                direction = trend_direction(trend_df.loc[m])
                md.append(f"- **{m}**: {direction}")
        md.append("")
    else:
        md.append("*趋势数据不足*\n")

    # ===== 5. 同行比较 =====
    md.append("\n## 五、同行业比较\n")
    if compare_df is not None and not compare_df.empty and len(compare_df.columns) > 1:
        target_col = compare_df.columns[0]
        peers = compare_df.columns[1:]
        md.append(f"对比对象: {', '.join(peers)}\n")

        key_metrics = ["净利率 (Net Margin)", "ROE 净资产收益率", "ROA 总资产收益率",
                       "总资产周转率", "资产负债率", "流动比率"]
        for m in key_metrics:
            if m not in compare_df.index:
                continue
            target_v = compare_df.loc[m, target_col]
            peer_vals = compare_df.loc[m].drop(target_col).dropna()
            if pd.isna(target_v) or len(peer_vals) == 0:
                continue
            peer_mean = peer_vals.mean()
            is_pct = any(kw in m for kw in ["率", "ROE", "ROA", "Margin"])

            lower_better = m in LOWER_IS_BETTER
            if lower_better:
                comparison = "优于" if target_v < peer_mean else "高于"
            else:
                comparison = "优于" if target_v > peer_mean else "低于"

            t_str = fmt_pct(target_v) if is_pct else fmt_num(target_v)
            p_str = fmt_pct(peer_mean) if is_pct else fmt_num(peer_mean)
            md.append(f"- **{m}**: 公司 {t_str},同行均值 {p_str} → {comparison}同行")
        md.append("")
    else:
        md.append("*未提供同行数据或同行数据不足*\n")

    # ===== 6. 基准评级总结 =====
    md.append("\n## 六、基准评级总结\n")
    rating_table = []
    for ratio_name in GENERIC_BENCHMARKS.keys():
        if ratio_name in ratios:
            v = ratios[ratio_name]
            rating = evaluate_against_benchmark(ratio_name, v)
            # 比率 / Margin 是百分比;但"流动比率""速动比率""周转率""倍数"不是
            is_pct = (any(kw in ratio_name for kw in ["ROE", "ROA", "Margin"]) or
                      ("率" in ratio_name and not any(
                          kw in ratio_name for kw in ["流动比率", "速动比率", "周转率"])))
            display_v = fmt_pct(v) if is_pct else fmt_num(v)
            rating_table.append(f"| {ratio_name} | {display_v} | {rating} |")

    if rating_table:
        md.append("| 指标 | 公司值 | 评级 |")
        md.append("|------|--------|------|")
        md.extend(rating_table)
    md.append("")

    # ===== 7. 综合评价 =====
    md.append("\n## 七、综合评价与建议\n")
    pros, cons = [], []

    if roe is not None:
        if roe > 0.15:
            pros.append(f"ROE 达 {fmt_pct(roe)},盈利效率突出")
        elif roe < 0.05:
            cons.append(f"ROE 仅 {fmt_pct(roe)},股东回报偏低")

    if nm is not None:
        if nm > 0.15:
            pros.append(f"净利率 {fmt_pct(nm)} 处于较高水平")
        elif nm < 0.03:
            cons.append(f"净利率仅 {fmt_pct(nm)},盈利空间受压")

    if da is not None:
        if da > 0.70:
            cons.append(f"资产负债率 {fmt_pct(da)},杠杆偏高,需关注偿债压力")
        elif da < 0.30:
            pros.append(f"资产负债率 {fmt_pct(da)},财务结构稳健")

    if cr is not None:
        if cr < 1.0:
            cons.append(f"流动比率仅 {fmt_num(cr)},短期流动性偏紧")

    ato = ratios.get("总资产周转率")
    if ato is not None and ato > 1.0:
        pros.append(f"总资产周转率 {fmt_num(ato)} 次,资产运用高效")

    if pros:
        md.append("**优势**:")
        for p in pros:
            md.append(f"- ✅ {p}")
        md.append("")
    if cons:
        md.append("**风险/不足**:")
        for c in cons:
            md.append(f"- ⚠️ {c}")
        md.append("")
    if not pros and not cons:
        md.append("*指标整体表现中性*\n")

    md.append("\n---\n")
    md.append(f"*本报告基于 yfinance 公开财务数据自动生成,仅供参考,不构成投资建议。*")

    return "\n".join(md)
