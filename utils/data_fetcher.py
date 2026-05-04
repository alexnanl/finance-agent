"""
财务数据获取模块
使用 yfinance 获取全球上市公司的财报数据
"""
import yfinance as yf
import pandas as pd
import time
import random
from typing import Optional, Dict, List
import streamlit as st


def _yf_call_with_retry(func, *args, max_retries=3, **kwargs):
    """
    yfinance 调用包装器,带自动重试 + 指数退避。
    用于绕过 Yahoo Finance 的 rate limit。
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            # 限流类错误才重试
            if "rate" in err_str or "429" in err_str or "too many" in err_str:
                # 指数退避: 1s, 3s, 7s + 随机抖动
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                time.sleep(wait)
                continue
            # 其他错误直接抛
            raise
    raise last_err


# 行业候选池 — 每个 sector 对应一批主要公司,用于"同行业+同规模"筛选
INDUSTRY_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSM", "ORCL", "ADBE",
                   "CRM", "AVGO", "AMD", "INTC", "CSCO", "QCOM", "IBM", "TXN",
                   "INTU", "NOW", "PLTR", "SNOW", "DDOG", "0700.HK", "9988.HK",
                   "1810.HK", "002415.SZ"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "TJX",
                          "BKNG", "CMG", "ABNB", "F", "GM", "MAR", "9618.HK",
                          "3690.HK", "1211.HK"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK",
                           "SCHW", "PYPL", "V", "MA", "BRK-B", "0005.HK",
                           "2318.HK", "1398.HK", "0939.HK", "600036.SS", "601318.SS"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT",
                   "DHR", "BMY", "AMGN", "GILD", "CVS", "MDT", "ISRG"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "VZ", "T", "CMCSA",
                                "TMUS", "CHTR", "EA", "TTWO", "0700.HK", "9988.HK"],
    "Consumer Defensive": ["WMT", "PG", "KO", "PEP", "COST", "MDLZ", "PM", "CL",
                           "KMB", "GIS", "K", "STZ", "600519.SS", "000858.SZ"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "OXY", "VLO",
               "601857.SS", "600028.SS"],
    "Industrials": ["BA", "CAT", "HON", "UPS", "GE", "RTX", "LMT", "DE", "MMM",
                    "EMR", "ETN", "ITW", "CSX", "NSC", "FDX"],
    "Basic Materials": ["LIN", "SHW", "FCX", "NEM", "ECL", "APD", "DD", "DOW", "PPG"],
    "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR"],
    "Utilities": ["NEE", "SO", "DUK", "AEP", "EXC", "SRE", "D", "PCG", "XEL"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_company_info(ticker: str) -> Dict:
    """获取公司基本信息(带 rate-limit 重试)"""
    try:
        def _do_fetch():
            tk = yf.Ticker(ticker)
            return tk.info or {}

        info = _yf_call_with_retry(_do_fetch)
        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName") or ticker.upper(),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "currency": info.get("financialCurrency", info.get("currency", "USD")),
            "market_cap": info.get("marketCap"),
            "summary": info.get("longBusinessSummary", ""),
            "exchange": info.get("exchange", "N/A"),
            "website": info.get("website", ""),
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "name": ticker.upper(), "error": str(e)}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financials(ticker: str) -> Dict[str, pd.DataFrame]:
    """
    获取年度三大报表(带 rate-limit 重试)
    返回: {'income': 利润表, 'balance': 资产负债表, 'cashflow': 现金流量表}
    """
    try:
        def _do_fetch():
            tk = yf.Ticker(ticker)
            return {
                "income": tk.financials if tk.financials is not None else pd.DataFrame(),
                "balance": tk.balance_sheet if tk.balance_sheet is not None else pd.DataFrame(),
                "cashflow": tk.cashflow if tk.cashflow is not None else pd.DataFrame(),
            }

        return _yf_call_with_retry(_do_fetch)
    except Exception as e:
        return {
            "income": pd.DataFrame(),
            "balance": pd.DataFrame(),
            "cashflow": pd.DataFrame(),
            "error": str(e),
        }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_price(ticker: str, period: str = "5y") -> pd.DataFrame:
    """获取股价历史"""
    try:
        tk = yf.Ticker(ticker)
        return tk.history(period=period)
    except Exception:
        return pd.DataFrame()


def get_peer_suggestions(sector: str, exclude: str = "") -> List[str]:
    """根据行业返回候选池(旧 API,保留兼容)"""
    peers = INDUSTRY_PEERS.get(sector, [])
    return [p for p in peers if p.upper() != exclude.upper()]


@st.cache_data(ttl=3600, show_spinner=False)
def _get_market_cap_for_ticker(ticker: str) -> Optional[float]:
    """轻量获取市值,用于规模匹配。失败返回 None。"""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        return info.get("marketCap")
    except Exception:
        return None


def get_peer_suggestions_by_size(sector: str, target_market_cap: Optional[float],
                                    exclude: str = "", n: int = 4,
                                    size_tolerance: float = 3.0) -> List[Dict]:
    """
    按"行业 + 规模"筛选同行
    - sector: 目标公司所属行业
    - target_market_cap: 目标公司市值
    - exclude: 排除的 ticker
    - n: 返回几个
    - size_tolerance: 市值容忍倍数(默认 3 倍 → 1/3x ~ 3x)
    返回: [{'ticker': 'MSFT', 'market_cap': 3.5e12, 'size_ratio': 1.05}, ...]
    """
    candidates = INDUSTRY_PEERS.get(sector, [])
    candidates = [c for c in candidates if c.upper() != (exclude or "").upper()]

    if not target_market_cap:
        return [{"ticker": c, "market_cap": None, "size_ratio": None}
                for c in candidates[:n]]

    import math
    scored = []
    for c in candidates:
        cap = _get_market_cap_for_ticker(c)
        if cap is None or cap <= 0:
            continue
        ratio = cap / target_market_cap
        if (1.0 / size_tolerance) <= ratio <= size_tolerance:
            scored.append({"ticker": c, "market_cap": cap, "size_ratio": ratio})

    scored.sort(key=lambda x: abs(math.log(x["size_ratio"])))

    # 不够 n 个时,放宽筛选
    if len(scored) < n:
        already = {s["ticker"] for s in scored}
        backup = []
        for c in candidates:
            if c in already:
                continue
            cap = _get_market_cap_for_ticker(c)
            if cap is None:
                continue
            ratio = cap / target_market_cap
            backup.append({"ticker": c, "market_cap": cap, "size_ratio": ratio})
        backup.sort(key=lambda x: abs(math.log(x["size_ratio"])))
        scored.extend(backup[: n - len(scored)])

    return scored[:n]


# 常用公司中英文名 → ticker 速查表(覆盖主流大盘股,避免每次走网络搜索)
COMMON_NAME_MAP = {
    # 美股
    "苹果": "AAPL", "apple": "AAPL",
    "微软": "MSFT", "microsoft": "MSFT",
    "谷歌": "GOOGL", "google": "GOOGL", "alphabet": "GOOGL",
    "亚马逊": "AMZN", "amazon": "AMZN",
    "脸书": "META", "facebook": "META", "meta": "META",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "英伟达": "NVDA", "nvidia": "NVDA",
    "奈飞": "NFLX", "网飞": "NFLX", "netflix": "NFLX",
    "沃尔玛": "WMT", "walmart": "WMT",
    "可口可乐": "KO", "coca cola": "KO", "coca-cola": "KO",
    "百事": "PEP", "pepsi": "PEP", "pepsico": "PEP",
    "麦当劳": "MCD", "mcdonalds": "MCD", "mcdonald's": "MCD",
    "星巴克": "SBUX", "starbucks": "SBUX",
    "迪士尼": "DIS", "disney": "DIS",
    "耐克": "NKE", "nike": "NKE",
    "波音": "BA", "boeing": "BA",
    "摩根大通": "JPM", "jpmorgan": "JPM", "jp morgan": "JPM",
    "高盛": "GS", "goldman sachs": "GS", "goldman": "GS",
    "美国银行": "BAC", "bank of america": "BAC",
    "强生": "JNJ", "johnson & johnson": "JNJ", "johnson and johnson": "JNJ",
    "辉瑞": "PFE", "pfizer": "PFE",
    "英特尔": "INTC", "intel": "INTC",
    "AMD": "AMD", "超微": "AMD",
    "甲骨文": "ORCL", "oracle": "ORCL",
    "ibm": "IBM",
    "思科": "CSCO", "cisco": "CSCO",
    "高通": "QCOM", "qualcomm": "QCOM",
    "雪佛龙": "CVX", "chevron": "CVX",
    "埃克森美孚": "XOM", "exxon": "XOM", "exxonmobil": "XOM",
    "台积电": "TSM", "tsmc": "TSM",
    "berkshire": "BRK-B", "伯克希尔": "BRK-B", "巴菲特": "BRK-B",
    # 港股
    "腾讯": "0700.HK", "tencent": "0700.HK",
    "阿里巴巴": "9988.HK", "阿里": "9988.HK", "alibaba": "9988.HK",
    "小米": "1810.HK", "xiaomi": "1810.HK",
    "美团": "3690.HK", "meituan": "3690.HK",
    "京东": "9618.HK", "jd": "9618.HK",
    "中国平安": "2318.HK", "ping an": "2318.HK",
    "工商银行": "1398.HK", "icbc": "1398.HK",
    "建设银行": "0939.HK", "ccb": "0939.HK",
    "比亚迪": "1211.HK", "byd": "1211.HK",
    "汇丰": "0005.HK", "hsbc": "0005.HK",
    # A股
    "贵州茅台": "600519.SS", "茅台": "600519.SS", "moutai": "600519.SS",
    "五粮液": "000858.SZ", "wuliangye": "000858.SZ",
    "招商银行": "600036.SS", "cmb": "600036.SS",
    "中国石油": "601857.SS", "petrochina": "601857.SS",
    "中国石化": "600028.SS", "sinopec": "600028.SS",
    "宁德时代": "300750.SZ", "catl": "300750.SZ",
    "海康威视": "002415.SZ", "hikvision": "002415.SZ",
    "中国平安a": "601318.SS",
    # 日股
    "丰田": "7203.T", "toyota": "7203.T",
    "索尼": "6758.T", "sony": "6758.T",
    "任天堂": "7974.T", "nintendo": "7974.T",
    "本田": "7267.T", "honda": "7267.T",
    # 欧股
    "lvmh": "MC.PA", "路威酩轩": "MC.PA",
    "asml": "ASML", "阿斯麦": "ASML",
    "sap": "SAP",
    "西门子": "SIE.DE", "siemens": "SIE.DE",
    "雀巢": "NESN.SW", "nestle": "NESN.SW",
}


def looks_like_ticker(s: str) -> bool:
    """
    判断输入是否像股票代码:
    - 长度 1-12,无空格
    - 只含 ASCII 字母/数字/点/横线(中文等非 ASCII 字符直接排除)
    - 必须是「全大写」或「含数字」(避免把 'Apple' 当成 ticker)
    """
    s = (s or "").strip()
    if not s or len(s) > 12 or " " in s:
        return False
    # 必须全是 ASCII
    if not s.isascii():
        return False
    # 只允许字母/数字/点/横线
    if not all(c.isalnum() or c in ".-" for c in s):
        return False
    has_digit = any(c.isdigit() for c in s)
    has_lower = any(c.islower() for c in s)
    # 含数字 → 是 ticker(如 0700.HK、600519.SS)
    # 不含数字但有小写字母 → 不是 ticker(如 Apple、Tesla)
    # 全大写无数字 → 是 ticker(如 AAPL、MSFT)
    if has_digit:
        return True
    return not has_lower


@st.cache_data(ttl=86400, show_spinner=False)
def search_ticker_by_name(query: str) -> List[Dict]:
    """
    通过公司名搜索 ticker
    优先查本地速查表(快速 + 不依赖外部 API),查不到则调用 Yahoo Finance 搜索接口
    返回: [{'ticker': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NMS', 'type': 'EQUITY'}, ...]
    """
    q = (query or "").strip()
    if not q:
        return []

    results = []
    seen_tickers = set()

    # 1) 本地速查表 - 精确匹配(最优先)
    q_lower = q.lower()
    if q_lower in COMMON_NAME_MAP:
        ticker = COMMON_NAME_MAP[q_lower]
        if ticker not in seen_tickers:
            results.append({
                "ticker": ticker,
                "name": q,  # 直接用用户输入的名字
                "exchange": _guess_exchange_from_ticker(ticker),
                "type": "EQUITY",
            })
            seen_tickers.add(ticker)

    # 2) 本地速查表 - 模糊匹配(用户输入是某个 key 的子串,或反之)
    if len(q_lower) >= 2:  # 避免 1 个字母的太宽泛匹配
        for key, ticker in COMMON_NAME_MAP.items():
            if ticker in seen_tickers:
                continue
            # 用户输入包含在 key 中,或 key 包含在用户输入中
            if q_lower in key.lower() or key.lower() in q_lower:
                results.append({
                    "ticker": ticker,
                    "name": key,
                    "exchange": _guess_exchange_from_ticker(ticker),
                    "type": "EQUITY",
                })
                seen_tickers.add(ticker)
                if len(results) >= 5:  # 速查表最多返回 5 条
                    break

    # 3) Yahoo Finance 搜索接口(覆盖速查表之外的公司)
    try:
        import requests
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(url, params={"q": q, "quotesCount": 6, "newsCount": 0},
                             headers=headers, timeout=8)
        if resp.ok:
            data = resp.json()
            for item in data.get("quotes", []):
                if item.get("quoteType") not in ("EQUITY",):
                    continue
                ticker = item.get("symbol", "")
                if not ticker or ticker in seen_tickers:
                    continue
                results.append({
                    "ticker": ticker,
                    "name": item.get("longname") or item.get("shortname") or ticker,
                    "exchange": item.get("exchDisp") or item.get("exchange", ""),
                    "type": item.get("quoteType", ""),
                })
                seen_tickers.add(ticker)
    except Exception:
        pass  # 搜索失败不影响速查表结果

    return results[:8]  # 最多返回 8 条


def _guess_exchange_from_ticker(ticker: str) -> str:
    """根据 ticker 后缀推测交易所"""
    if "." not in ticker:
        return "NASDAQ/NYSE"  # 美股大概率
    suffix = ticker.split(".")[-1]
    return {
        "HK": "HKEX",
        "SS": "Shanghai",
        "SZ": "Shenzhen",
        "T": "Tokyo",
        "L": "London",
        "DE": "XETRA",
        "PA": "Paris",
        "MI": "Milan",
        "AS": "Amsterdam",
    }.get(suffix, suffix)
