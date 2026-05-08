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
    """获取股价历史(带 rate-limit 重试)"""
    try:
        def _do_fetch():
            tk = yf.Ticker(ticker)
            return tk.history(period=period)

        return _yf_call_with_retry(_do_fetch)
    except Exception:
        return pd.DataFrame()


def get_peer_suggestions(sector: str, exclude: str = "") -> List[str]:
    """根据行业返回候选池(旧 API,保留兼容)"""
    peers = INDUSTRY_PEERS.get(sector, [])
    return [p for p in peers if p.upper() != exclude.upper()]


@st.cache_data(ttl=3600, show_spinner=False)
def _get_market_cap_for_ticker(ticker: str) -> Optional[float]:
    """轻量获取市值,用于规模匹配。带 rate-limit 重试。失败返回 None。

    ★ 重要:这个函数被 get_peer_suggestions_by_size 调用,
       如果没 retry,Yahoo 限流时同行的市值都拿不到 → AI 推荐的真同行
       会被淘汰,池子里的伪同行(麦当劳/TJX)反而胜出。
    """
    try:
        def _do_fetch():
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            return info.get("marketCap")

        return _yf_call_with_retry(_do_fetch, max_retries=2)  # 同行用 2 次重试,避免太慢
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _ai_suggest_peers(company_name: str, ticker: str, sector: str,
                       industry: str, country: str,
                       market_cap: Optional[float], n: int = 5) -> List[str]:
    """
    用 LLM 智能推荐同行公司
    返回 ticker 列表,如 ['000333.SZ', 'WHR', 'ELUXY', ...]
    """
    # 获取 API Key
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        pass
    if not api_key:
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []

    try:
        from openai import OpenAI
        import json as _json

        client = OpenAI(api_key=api_key)

        market_cap_desc = ""
        if market_cap:
            if market_cap > 1e11:
                market_cap_desc = f"市值约 {market_cap/1e9:.0f}B(超大盘)"
            elif market_cap > 1e10:
                market_cap_desc = f"市值约 {market_cap/1e9:.0f}B(大盘)"
            else:
                market_cap_desc = f"市值约 {market_cap/1e9:.1f}B(中小盘)"

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是金融行业分析师,精通全球上市公司分类。"
                        "用户给你一家公司的信息,你推荐它最直接的竞争对手/同行业可比公司。"
                        "\n\n"
                        "**核心原则**:\n"
                        "1. **细分赛道**优先 — 比如海尔做白色家电,推荐美的、格力、Whirlpool,而不是麦当劳\n"
                        "2. **规模相近** — 优先推荐市值在目标公司 1/3x 到 3x 范围的\n"
                        "3. **市场多元** — 兼顾本国市场 + 海外市场代表(更专业)\n"
                        "4. **真实可比** — 必须是同业务模式的公司,不能只是同 sector\n"
                        "\n"
                        "**ticker 格式严格遵守 Yahoo Finance**:\n"
                        "- 美股直接代码: AAPL, WHR\n"
                        "- 港股带 .HK: 0700.HK\n"
                        "- 上交所 .SS: 600519.SS\n"
                        "- 深交所 .SZ: 000333.SZ\n"
                        "- 日股 .T,韩股 .KS,英股 .L,德股 .DE,法股 .PA,瑞士 .SW\n"
                        "\n"
                        "返回 JSON: {\"peers\": [\"ticker1\", \"ticker2\", ...]}\n"
                        "**只返回 ticker,不要公司名,不要解释**"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"目标公司:{company_name} ({ticker})\n"
                        f"行业:{sector} / {industry}\n"
                        f"国家:{country}\n"
                        f"{market_cap_desc}\n"
                        f"\n请推荐 {n} 家最直接的同行竞争对手。"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        result = _json.loads(resp.choices[0].message.content or "{}")
        peers = result.get("peers", [])
        # 过滤无效 ticker(空字符串、太长等)
        peers = [p for p in peers if p and isinstance(p, str) and len(p) <= 12]
        # 排除目标公司自己
        peers = [p for p in peers if p.upper() != ticker.upper()]
        # 调试:成功时在控制台打印,方便部署后排查
        try:
            import sys
            print(f"[_ai_suggest_peers] {company_name}({ticker}) → {peers[:n]}",
                   file=sys.stderr, flush=True)
        except Exception:
            pass
        return peers[:n]
    except Exception as e:
        # 调试:失败时在控制台打印,方便部署后排查
        try:
            import sys
            print(f"[_ai_suggest_peers] FAILED for {company_name}({ticker}): "
                   f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        except Exception:
            pass
        return []


def get_peer_suggestions_by_size(sector: str, target_market_cap: Optional[float],
                                    exclude: str = "", n: int = 4,
                                    size_tolerance: float = 3.0,
                                    company_name: str = "",
                                    industry: str = "",
                                    country: str = "") -> List[Dict]:
    """
    按"行业 + 规模"筛选同行 — 优先用 LLM 智能推荐,失败 fallback 到硬编码池

    ★ 关键设计:AI 推荐的同行**永远排在 INDUSTRY_PEERS 池子之前**,
       即使市值差距大也不会被池子里的"伪同行"挤掉。
       池子只在 AI 推荐不够 n 个时补位。

    - sector: 目标公司所属 sector
    - target_market_cap: 目标公司市值
    - exclude: 排除的 ticker
    - n: 返回几个
    - size_tolerance: 市值容忍倍数(默认 3 倍 → 1/3x ~ 3x)
    - company_name / industry / country: 用于 LLM 智能推荐
    返回: [{'ticker': 'MSFT', 'market_cap': 3.5e12, 'size_ratio': 1.05}, ...]
    """
    import math

    # ===== 优先级 1:LLM 智能推荐 =====
    ai_peers = []
    if company_name and (industry or sector):
        ai_peers = _ai_suggest_peers(
            company_name=company_name,
            ticker=exclude or "",
            sector=sector or "",
            industry=industry or "",
            country=country or "",
            market_cap=target_market_cap,
            n=n + 2,  # 多要几个,后面 fallback 用
        )
    # 去重 + 排除自己
    ai_peers_clean = []
    seen_ai = set()
    for p in ai_peers:
        pu = p.upper()
        if pu in seen_ai or pu == (exclude or "").upper():
            continue
        seen_ai.add(pu)
        ai_peers_clean.append(p)

    # ===== 优先级 2:行业池(只在 AI 推荐不够时用)=====
    pool_peers = []
    seen_pool = set(seen_ai) | {(exclude or "").upper()}
    for p in INDUSTRY_PEERS.get(sector, []):
        if p.upper() in seen_pool:
            continue
        seen_pool.add(p.upper())
        pool_peers.append(p)

    # ===== 没有 target_market_cap 时,直接返回 AI 优先列表 =====
    if not target_market_cap:
        all_picked = ai_peers_clean[:n]
        if len(all_picked) < n:
            all_picked.extend(pool_peers[: n - len(all_picked)])
        return [{"ticker": c, "market_cap": None, "size_ratio": None}
                for c in all_picked[:n]]

    # ===== 阶段 A:把 AI 推荐转成 scored 结构 =====
    # 关键:AI 推荐的同行,只要市值能拿到就保留
    # 不像之前那样被 size_tolerance 过滤 — AI 已经判断过业务相关性了
    ai_scored = []
    for c in ai_peers_clean:
        cap = _get_market_cap_for_ticker(c)
        if cap is None or cap <= 0:
            # 拿不到市值的也保留(用 None,不参与排序但占名额)
            ai_scored.append({"ticker": c, "market_cap": None, "size_ratio": None,
                                "_source": "ai", "_sort_key": 999})
            continue
        ratio = cap / target_market_cap
        ai_scored.append({"ticker": c, "market_cap": cap, "size_ratio": ratio,
                            "_source": "ai", "_sort_key": abs(math.log(ratio))})

    # AI 推荐内部按规模接近度排序(但不会被淘汰)
    ai_scored.sort(key=lambda x: x["_sort_key"])

    # 如果 AI 推荐已经够 n 个,直接返回(完全不用池子)
    if len(ai_scored) >= n:
        result = []
        for s in ai_scored[:n]:
            result.append({"ticker": s["ticker"],
                            "market_cap": s["market_cap"],
                            "size_ratio": s["size_ratio"]})
        return result

    # ===== 阶段 B:AI 推荐不够 n 个,用池子补位 =====
    # 池子里的同行用 size_tolerance 严格筛选(避免 MCD 这种超大盘乱入)
    pool_scored = []
    for c in pool_peers:
        cap = _get_market_cap_for_ticker(c)
        if cap is None or cap <= 0:
            continue
        ratio = cap / target_market_cap
        if (1.0 / size_tolerance) <= ratio <= size_tolerance:
            pool_scored.append({"ticker": c, "market_cap": cap, "size_ratio": ratio,
                                  "_sort_key": abs(math.log(ratio))})
    pool_scored.sort(key=lambda x: x["_sort_key"])

    # 还不够 n 个,再放宽 size 限制
    if len(ai_scored) + len(pool_scored) < n:
        already = {s["ticker"] for s in pool_scored}
        backup = []
        for c in pool_peers:
            if c in already:
                continue
            cap = _get_market_cap_for_ticker(c)
            if cap is None:
                continue
            ratio = cap / target_market_cap
            backup.append({"ticker": c, "market_cap": cap, "size_ratio": ratio,
                            "_sort_key": abs(math.log(ratio))})
        backup.sort(key=lambda x: x["_sort_key"])
        pool_scored.extend(backup[: n - len(ai_scored) - len(pool_scored)])

    # ===== 合并:AI 优先 + 池子补位 =====
    final = []
    for s in ai_scored + pool_scored:
        final.append({"ticker": s["ticker"],
                       "market_cap": s["market_cap"],
                       "size_ratio": s["size_ratio"]})
        if len(final) >= n:
            break

    return final[:n]


# 常用公司中英文名 → ticker 速查表(覆盖主流大盘股,避免每次走网络搜索)
COMMON_NAME_MAP = {
    # ===== 美股 - 科技 =====
    "苹果": "AAPL", "apple": "AAPL",
    "微软": "MSFT", "microsoft": "MSFT",
    "谷歌": "GOOGL", "google": "GOOGL", "alphabet": "GOOGL",
    "亚马逊": "AMZN", "amazon": "AMZN",
    "脸书": "META", "facebook": "META", "meta": "META",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "英伟达": "NVDA", "nvidia": "NVDA",
    "奈飞": "NFLX", "网飞": "NFLX", "netflix": "NFLX",
    "英特尔": "INTC", "intel": "INTC",
    "AMD": "AMD", "超微": "AMD", "amd": "AMD",
    "甲骨文": "ORCL", "oracle": "ORCL",
    "ibm": "IBM", "国际商业机器": "IBM",
    "思科": "CSCO", "cisco": "CSCO",
    "高通": "QCOM", "qualcomm": "QCOM",
    "博通": "AVGO", "broadcom": "AVGO",
    "salesforce": "CRM",
    "adobe": "ADBE", "奥多比": "ADBE",
    "paypal": "PYPL", "贝宝": "PYPL",
    "uber": "UBER", "优步": "UBER",
    "airbnb": "ABNB", "爱彼迎": "ABNB",
    "snowflake": "SNOW",
    "palantir": "PLTR",
    "shopify": "SHOP",
    "spotify": "SPOT",
    "zoom": "ZM",

    # ===== 美股 - 消费 =====
    "沃尔玛": "WMT", "walmart": "WMT",
    "可口可乐": "KO", "coca cola": "KO", "coca-cola": "KO",
    "百事": "PEP", "pepsi": "PEP", "pepsico": "PEP",
    "麦当劳": "MCD", "mcdonalds": "MCD", "mcdonald's": "MCD",
    "星巴克": "SBUX", "starbucks": "SBUX",
    "迪士尼": "DIS", "disney": "DIS",
    "耐克": "NKE", "nike": "NKE",
    "阿迪达斯": "ADDYY", "adidas": "ADDYY",
    "宝洁": "PG", "p&g": "PG", "procter & gamble": "PG", "procter and gamble": "PG",
    "好市多": "COST", "costco": "COST",
    "塔吉特": "TGT", "target": "TGT",
    "家得宝": "HD", "home depot": "HD",
    "联合利华": "UL", "unilever": "UL",
    "卡夫亨氏": "KHC", "kraft heinz": "KHC",

    # ===== 美股 - 汽车 =====
    "福特": "F", "ford": "F",
    "通用汽车": "GM", "general motors": "GM",
    "克莱斯勒": "STLA", "stellantis": "STLA",
    "rivian": "RIVN", "rivian": "RIVN",
    "lucid": "LCID",

    # ===== 美股 - 金融 =====
    "摩根大通": "JPM", "jpmorgan": "JPM", "jp morgan": "JPM", "小摩": "JPM",
    "高盛": "GS", "goldman sachs": "GS", "goldman": "GS",
    "美国银行": "BAC", "bank of america": "BAC", "美银": "BAC",
    "富国银行": "WFC", "wells fargo": "WFC",
    "花旗": "C", "citi": "C", "citigroup": "C",
    "摩根士丹利": "MS", "morgan stanley": "MS", "大摩": "MS",
    "美国运通": "AXP", "american express": "AXP", "amex": "AXP",
    "贝莱德": "BLK", "blackrock": "BLK",
    "visa": "V", "维萨": "V",
    "mastercard": "MA", "万事达": "MA",
    "berkshire": "BRK-B", "伯克希尔": "BRK-B", "巴菲特": "BRK-B",

    # ===== 美股 - 医药/生物 =====
    "强生": "JNJ", "johnson & johnson": "JNJ", "johnson and johnson": "JNJ",
    "辉瑞": "PFE", "pfizer": "PFE",
    "默沙东": "MRK", "merck": "MRK",
    "礼来": "LLY", "eli lilly": "LLY", "lilly": "LLY",
    "雅培": "ABT", "abbott": "ABT",
    "艾伯维": "ABBV", "abbvie": "ABBV",
    "诺华": "NVS", "novartis": "NVS",
    "罗氏": "RHHBY", "roche": "RHHBY",
    "联合健康": "UNH", "unitedhealth": "UNH",

    # ===== 美股 - 能源 =====
    "雪佛龙": "CVX", "chevron": "CVX",
    "埃克森美孚": "XOM", "exxon": "XOM", "exxonmobil": "XOM",
    "壳牌": "SHEL", "shell": "SHEL",
    "bp": "BP",

    # ===== 美股 - 工业/航空 =====
    "波音": "BA", "boeing": "BA",
    "空客": "EADSY", "airbus": "EADSY",
    "卡特彼勒": "CAT", "caterpillar": "CAT",
    "通用电气": "GE", "general electric": "GE",
    "联邦快递": "FDX", "fedex": "FDX",
    "ups": "UPS",
    "delta airlines": "DAL", "达美航空": "DAL",
    "united airlines": "UAL", "美联航": "UAL",

    # ===== 美股 - 半导体 =====
    "台积电": "TSM", "tsmc": "TSM",
    "应用材料": "AMAT", "applied materials": "AMAT",
    "美光": "MU", "micron": "MU",

    # ===== 港股 =====
    "腾讯": "0700.HK", "tencent": "0700.HK",
    "阿里巴巴": "9988.HK", "阿里": "9988.HK", "alibaba": "9988.HK",
    "小米": "1810.HK", "xiaomi": "1810.HK",
    "美团": "3690.HK", "meituan": "3690.HK",
    "京东": "9618.HK", "jd": "9618.HK", "京东.hk": "9618.HK",
    "中国平安": "2318.HK", "ping an": "2318.HK",
    "工商银行": "1398.HK", "icbc": "1398.HK",
    "建设银行": "0939.HK", "ccb": "0939.HK",
    "比亚迪": "1211.HK", "byd": "1211.HK",
    "汇丰": "0005.HK", "hsbc": "0005.HK",
    "中国移动": "0941.HK", "china mobile": "0941.HK",
    "网易": "9999.HK", "netease": "9999.HK",
    "百度": "9888.HK", "baidu": "9888.HK",
    "快手": "1024.HK", "kuaishou": "1024.HK",
    "蔚来": "9866.HK", "nio": "9866.HK",
    "理想汽车": "2015.HK", "li auto": "2015.HK",
    "小鹏": "9868.HK", "xpeng": "9868.HK",

    # ===== A股 =====
    "贵州茅台": "600519.SS", "茅台": "600519.SS", "moutai": "600519.SS",
    "五粮液": "000858.SZ", "wuliangye": "000858.SZ",
    "招商银行": "600036.SS", "cmb": "600036.SS",
    "中国石油": "601857.SS", "petrochina": "601857.SS",
    "中国石化": "600028.SS", "sinopec": "600028.SS",
    "宁德时代": "300750.SZ", "catl": "300750.SZ",
    "海康威视": "002415.SZ", "hikvision": "002415.SZ",
    "中国平安a": "601318.SS",
    "比亚迪a": "002594.SZ",
    "万科a": "000002.SZ", "万科": "000002.SZ",
    "格力电器": "000651.SZ", "格力": "000651.SZ", "gree": "000651.SZ",
    "美的集团": "000333.SZ", "美的": "000333.SZ", "midea": "000333.SZ",
    "京东方": "000725.SZ", "boe": "000725.SZ",
    "工商银行a": "601398.SS",
    "建设银行a": "601939.SS",
    "中国人寿": "601628.SS",
    "中国神华": "601088.SS",
    "上汽集团": "600104.SS", "saic": "600104.SS",
    "三一重工": "600031.SS", "sany": "600031.SS",

    # ===== 日股 =====
    "丰田": "7203.T", "toyota": "7203.T",
    "索尼": "6758.T", "sony": "6758.T",
    "任天堂": "7974.T", "nintendo": "7974.T",
    "本田": "7267.T", "honda": "7267.T",
    "日产": "7201.T", "nissan": "7201.T",
    "马自达": "7261.T", "mazda": "7261.T",
    "三菱": "8058.T", "mitsubishi": "8058.T",
    "软银": "9984.T", "softbank": "9984.T",
    "优衣库": "9983.T", "uniqlo": "9983.T", "fast retailing": "9983.T",
    "佳能": "7751.T", "canon": "7751.T",

    # ===== 韩股 =====
    "三星": "005930.KS", "samsung": "005930.KS",
    "lg": "066570.KS",
    "现代": "005380.KS", "hyundai": "005380.KS",
    "起亚": "000270.KS", "kia": "000270.KS",
    "sk海力士": "000660.KS",

    # ===== 欧股 =====
    "lvmh": "MC.PA", "路威酩轩": "MC.PA",
    "asml": "ASML", "阿斯麦": "ASML",
    "sap": "SAP",
    "西门子": "SIE.DE", "siemens": "SIE.DE",
    "雀巢": "NESN.SW", "nestle": "NESN.SW",
    "诺和诺德": "NVO", "novo nordisk": "NVO",
    "阿斯利康": "AZN", "astrazeneca": "AZN",
    "葛兰素史克": "GSK", "glaxosmithkline": "GSK",
    "宝马": "BMW.DE", "bmw": "BMW.DE",
    "梅赛德斯": "MBG.DE", "mercedes": "MBG.DE", "奔驰": "MBG.DE",
    "大众": "VOW3.DE", "volkswagen": "VOW3.DE",
    "巴克莱": "BCS", "barclays": "BCS",
    "渣打": "STAN.L", "standard chartered": "STAN.L",
    "汇丰a": "HSBA.L",
    "壳牌伦": "SHEL.L",
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


def _ai_identify_ticker(query: str) -> Optional[Dict]:
    """
    最后的兜底:让 GPT 识别公司名 → ticker
    返回: {"ticker": "F", "name": "Ford Motor Company"} 或 None
    成本:每次约 $0.0005,缓存后基本零成本
    """
    # 检查是否有 OpenAI Key
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        pass
    if not api_key:
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        import json as _json

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个股票代码识别专家。用户给你公司名(中文或英文),"
                        "你返回该公司在 Yahoo Finance 上的股票代码格式。"
                        "重要规则:\n"
                        "- 美股直接给代码,如 'F'(福特)、'AAPL'(苹果)\n"
                        "- 港股带 .HK 后缀,如 '0700.HK'(腾讯)\n"
                        "- 上交所带 .SS,如 '600519.SS'(贵州茅台)\n"
                        "- 深交所带 .SZ,如 '000858.SZ'(五粮液)\n"
                        "- 日股带 .T,如 '7203.T'(丰田)\n"
                        "- 韩股带 .KS,如 '005930.KS'(三星)\n"
                        "- 英股带 .L,如 'HSBA.L'(汇丰)\n"
                        "- 德股带 .DE,如 'SAP.DE'(SAP)\n"
                        "- 法股带 .PA,如 'MC.PA'(LVMH)\n"
                        "如果该公司有多个上市地,优先返回主要交易所。\n"
                        "如果你不确定或公司未上市,返回 ticker=null。\n"
                        "返回 JSON 格式: {\"ticker\": \"代码\", \"name\": \"公司全称\"}"
                    ),
                },
                {"role": "user", "content": f"公司名:{query}"},
            ],
            temperature=0,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        result = _json.loads(resp.choices[0].message.content or "{}")
        ticker = result.get("ticker")
        if not ticker or ticker.lower() in ("null", "none", ""):
            return None
        return {
            "ticker": ticker,
            "name": result.get("name", query),
        }
    except Exception:
        return None


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

    # 4) 终极兜底:GPT 智能识别(速查表 + Yahoo 都没找到时)
    if not results:
        ai_result = _ai_identify_ticker(q)
        if ai_result and ai_result.get("ticker"):
            ticker = ai_result["ticker"]
            results.append({
                "ticker": ticker,
                "name": ai_result.get("name", q),
                "exchange": _guess_exchange_from_ticker(ticker),
                "type": "EQUITY",
                "source": "ai",  # 标记是 AI 识别的(可显示在 UI)
            })

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
