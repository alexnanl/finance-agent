"""
财务数据获取模块
使用 yfinance 获取全球上市公司的财报数据
"""
import yfinance as yf
import pandas as pd
from typing import Optional, Dict, List
import streamlit as st


# 简单的行业 → 同行龙头映射(可扩展)
# 用户找不到对标公司时可作为兜底建议
INDUSTRY_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "VZ"],
    "Consumer Defensive": ["WMT", "PG", "KO", "PEP", "COST"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Industrials": ["BA", "CAT", "HON", "UPS", "GE"],
    "Basic Materials": ["LIN", "SHW", "FCX", "NEM", "ECL"],
    "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA"],
    "Utilities": ["NEE", "SO", "DUK", "AEP", "EXC"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_company_info(ticker: str) -> Dict:
    """获取公司基本信息"""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
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
    获取年度三大报表
    返回: {'income': 利润表, 'balance': 资产负债表, 'cashflow': 现金流量表}
    """
    try:
        tk = yf.Ticker(ticker)
        return {
            "income": tk.financials if tk.financials is not None else pd.DataFrame(),
            "balance": tk.balance_sheet if tk.balance_sheet is not None else pd.DataFrame(),
            "cashflow": tk.cashflow if tk.cashflow is not None else pd.DataFrame(),
        }
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
    """根据行业返回同行龙头建议"""
    peers = INDUSTRY_PEERS.get(sector, [])
    return [p for p in peers if p.upper() != exclude.upper()]
