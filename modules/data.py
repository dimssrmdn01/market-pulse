"""
data.py
Handles all data acquisition: FOMC meeting calendar, historical Fed Funds Rate
(via FRED), and market-implied rate-move probabilities derived from
30-Day Fed Funds futures (CME ZQ contracts via Yahoo Finance).

No API key is required for FRED's public CSV endpoint or for Yahoo Finance.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import requests
import yfinance as yf
import streamlit as st

FRED_SERIES_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

# Official FOMC meeting calendar. The Fed publishes this a year ahead, so it
# is safe to hardcode and refresh once a year rather than scrape a page that
# can change structure without warning.
FOMC_CALENDAR_2026 = [
    {"start": "2026-01-27", "end": "2026-01-28", "sep": False},
    {"start": "2026-03-17", "end": "2026-03-18", "sep": True},
    {"start": "2026-04-28", "end": "2026-04-29", "sep": False},
    {"start": "2026-06-16", "end": "2026-06-17", "sep": True},
    {"start": "2026-07-28", "end": "2026-07-29", "sep": False},
    {"start": "2026-09-15", "end": "2026-09-16", "sep": True},
    {"start": "2026-10-27", "end": "2026-10-28", "sep": False},
    {"start": "2026-12-08", "end": "2026-12-09", "sep": True},
]

# Manual fallback used only if the live FRED fetch fails (e.g. no internet
# in a restricted sandbox). Kept short - just enough for the app to render.
FALLBACK_RATE_HISTORY = pd.DataFrame(
    {
        "date": pd.to_datetime(
            [
                "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29",
                "2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29",
                "2026-06-17",
            ]
        ),
        "rate_upper": [4.50, 4.50, 4.25, 4.00, 3.75, 3.75, 3.75, 3.75, 3.75],
    }
)

CURRENT_TARGET_RANGE = (3.50, 3.75)  

# Multi-asset ticker strip: crypto, forex, komoditas, indeks saham global & saham Indonesia
CATEGORY_LABELS = {
    "crypto":    {"ID": "Kripto", "EN": "Crypto"},
    "forex":     {"ID": "Forex", "EN": "Forex"},
    "commodity": {"ID": "Komoditas", "EN": "Commodities"},
    "stock":     {"ID": "Indeks Saham Global", "EN": "Global Equity Indices"},
    "idx_stock": {"ID": "Saham Indonesia", "EN": "Indonesian Stocks"},
}

# Urutan tampil 
CATEGORY_ORDER = ["crypto", "forex", "commodity", "stock", "idx_stock"]

AVAILABLE_ASSETS = {
    # --- Kripto ---
    "BTC/USD":  {"symbol": "BTC-USD",  "category": "crypto"},
    "ETH/USD":  {"symbol": "ETH-USD",  "category": "crypto"},
    "SOL/USD":  {"symbol": "SOL-USD",  "category": "crypto"},
    "BNB/USD":  {"symbol": "BNB-USD",  "category": "crypto"},
    "XRP/USD":  {"symbol": "XRP-USD",  "category": "crypto"},
    "ADA/USD":  {"symbol": "ADA-USD",  "category": "crypto"},
    "DOGE/USD": {"symbol": "DOGE-USD", "category": "crypto"},
    "AVAX/USD": {"symbol": "AVAX-USD", "category": "crypto"},

    # --- Forex ---
    "EUR/USD": {"symbol": "EURUSD=X", "category": "forex"},
    "GBP/USD": {"symbol": "GBPUSD=X", "category": "forex"},
    "USD/JPY": {"symbol": "USDJPY=X", "category": "forex"},
    "USD/CHF": {"symbol": "USDCHF=X", "category": "forex"},
    "AUD/USD": {"symbol": "AUDUSD=X", "category": "forex"},
    "USD/CAD": {"symbol": "USDCAD=X", "category": "forex"},
    "USD/CNY": {"symbol": "USDCNY=X", "category": "forex"},
    "USD/IDR": {"symbol": "USDIDR=X", "category": "forex"},

    # --- Komoditas ---
    "Emas (Gold)":    {"symbol": "GC=F", "category": "commodity"},
    "Perak (Silver)": {"symbol": "SI=F", "category": "commodity"},
    "Minyak (WTI)":   {"symbol": "CL=F", "category": "commodity"},
    "Minyak (Brent)": {"symbol": "BZ=F", "category": "commodity"},
    "Gas Alam":       {"symbol": "NG=F", "category": "commodity"},
    "Tembaga":        {"symbol": "HG=F", "category": "commodity"},

    # --- Indeks Saham Global ---
    "S&P 500":          {"symbol": "^GSPC",  "category": "stock"},
    "Nasdaq Composite": {"symbol": "^IXIC",  "category": "stock"},
    "Nasdaq 100":       {"symbol": "NDX",    "category": "stock"},
    "Dow Jones":        {"symbol": "^DJI",   "category": "stock"},
    "Russell 2000":     {"symbol": "^RUT",   "category": "stock"},
    "FTSE 100":         {"symbol": "^FTSE",  "category": "stock"},
    "Nikkei 225":       {"symbol": "^N225",  "category": "stock"},
    "DAX":              {"symbol": "^GDAXI", "category": "stock"},

    # --- Saham Indonesia (IDX, top market cap) ---
    "IHSG (JKSE)":       {"symbol": "^JKSE",   "category": "idx_stock"},
    "BCA (BBCA)":        {"symbol": "BBCA.JK", "category": "idx_stock"},
    "Bank Mandiri (BMRI)": {"symbol": "BMRI.JK", "category": "idx_stock"},
    "BRI (BBRI)":        {"symbol": "BBRI.JK", "category": "idx_stock"},
    "Telkom (TLKM)":     {"symbol": "TLKM.JK", "category": "idx_stock"},
    "Astra International (ASII)": {"symbol": "ASII.JK", "category": "idx_stock"},
    "Bank Negara Indonesia (BBNI)": {"symbol": "BBNI.JK", "category": "idx_stock"},
    "Unilever Indonesia (UNVR)": {"symbol": "UNVR.JK", "category": "idx_stock"},
}


def get_assets_grouped() -> dict[str, list[str]]:
    """Kelompokkan label aset per kategori, urutan sesuai CATEGORY_ORDER."""
    grouped: dict[str, list[str]] = {cat: [] for cat in CATEGORY_ORDER}
    for label, meta in AVAILABLE_ASSETS.items():
        grouped.setdefault(meta["category"], []).append(label)
    return grouped

def format_price(price: float, category: str) -> str:
    """Format a price sensibly per asset class (crypto/stock vs. forex pairs)."""
    if category == "forex":
        return f"{price:,.0f}" if price > 100 else f"{price:.4f}"
    if price >= 1000:
        return f"{price:,.0f}"
    return f"{price:,.2f}"

@st.cache_data(ttl=300)
def fetch_market_snapshot(selected_labels=None) -> list[dict]:
    """
    Pull a quick multi-asset snapshot via Yahoo Finance for the hero ticker strip,
    filtered by user selection.
    """
    if not selected_labels:
        selected_labels = ["BTC/USD", "Emas (Gold)", "EUR/USD", "S&P 500"]

    try:
        import yfinance as yf

        # Filter aset berdasarkan pilihan dropdown
        assets_to_fetch = [
            {"label": label, **AVAILABLE_ASSETS[label]}
            for label in selected_labels if label in AVAILABLE_ASSETS
        ]

        if not assets_to_fetch:
            return []

        symbols = [a["symbol"] for a in assets_to_fetch]
        raw = yf.download(
            symbols, period="5d", interval="1d", group_by="ticker",
            progress=False, threads=True, auto_adjust=True,
        )

        results = []
        for asset in assets_to_fetch:
            try:
                sym = asset["symbol"]
                closes = raw[sym]["Close"].dropna() if len(symbols) > 1 else raw["Close"].dropna()
                if len(closes) < 2:
                    continue
                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                change_pct = (last - prev) / prev * 100 if prev else 0.0
                results.append({**asset, "price": last, "change_pct": round(change_pct, 2)})
            except Exception:
                continue
        return results
    except Exception:
        return []


@dataclass
class ReleaseInfo:
    release_date: dt.date
    reference_month: str
    is_next: bool
    days_away: int


# Official 2026 release dates, straight from the U.S. Bureau of Labor
# Statistics schedule pages (published in advance, safe to hardcode and
# refresh yearly — same approach as the FOMC calendar above).
CPI_CALENDAR_2026 = [
    {"date": "2026-01-13", "reference_month": "Desember 2025"},
    {"date": "2026-02-13", "reference_month": "Januari 2026"},
    {"date": "2026-03-11", "reference_month": "Februari 2026"},
    {"date": "2026-04-10", "reference_month": "Maret 2026"},
    {"date": "2026-05-12", "reference_month": "April 2026"},
    {"date": "2026-06-10", "reference_month": "Mei 2026"},
    {"date": "2026-07-14", "reference_month": "Juni 2026"},
    {"date": "2026-08-12", "reference_month": "Juli 2026"},
    {"date": "2026-09-11", "reference_month": "Agustus 2026"},
    {"date": "2026-10-14", "reference_month": "September 2026"},
    {"date": "2026-11-10", "reference_month": "Oktober 2026"},
    {"date": "2026-12-10", "reference_month": "November 2026"},
]
# Source: https://www.bls.gov/schedule/news_release/cpi.htm

NFP_CALENDAR_2026 = [
    {"date": "2026-01-09", "reference_month": "Desember 2025"},
    {"date": "2026-02-11", "reference_month": "Januari 2026"},
    {"date": "2026-03-06", "reference_month": "Februari 2026"},
    {"date": "2026-04-03", "reference_month": "Maret 2026"},
    {"date": "2026-05-08", "reference_month": "April 2026"},
    {"date": "2026-06-05", "reference_month": "Mei 2026"},
    {"date": "2026-07-02", "reference_month": "Juni 2026"},
    {"date": "2026-08-07", "reference_month": "Juli 2026"},
    {"date": "2026-09-04", "reference_month": "Agustus 2026"},
    {"date": "2026-10-02", "reference_month": "September 2026"},
    {"date": "2026-11-06", "reference_month": "Oktober 2026"},
    {"date": "2026-12-04", "reference_month": "November 2026"},
]
# Source: https://www.bls.gov/schedule/news_release/empsit.htm


def get_release_schedule(calendar: list[dict], as_of: dt.date | None = None) -> list[ReleaseInfo]:
    """Generic helper for any BLS-style monthly release calendar (CPI, NFP, etc.)."""
    as_of = as_of or dt.date.today()
    releases = []
    next_found = False
    for r in calendar:
        release_date = dt.datetime.strptime(r["date"], "%Y-%m-%d").date()
        is_next = (not next_found) and (release_date >= as_of)
        if is_next:
            next_found = True
        releases.append(
            ReleaseInfo(
                release_date=release_date,
                reference_month=r["reference_month"],
                is_next=is_next,
                days_away=(release_date - as_of).days,
            )
        )
    return releases


@dataclass
class MeetingInfo:
    start: dt.date
    end: dt.date
    has_sep: bool
    is_next: bool
    days_away: int


def get_meeting_schedule(as_of: dt.date | None = None) -> list[MeetingInfo]:
    """Return the full 2026 FOMC calendar annotated with which meeting is next."""
    as_of = as_of or dt.date.today()
    meetings = []
    next_found = False
    for m in FOMC_CALENDAR_2026:
        end_date = dt.datetime.strptime(m["end"], "%Y-%m-%d").date()
        start_date = dt.datetime.strptime(m["start"], "%Y-%m-%d").date()
        is_next = (not next_found) and (end_date >= as_of)
        if is_next:
            next_found = True
        meetings.append(
            MeetingInfo(
                start=start_date,
                end=end_date,
                has_sep=m["sep"],
                is_next=is_next,
                days_away=(end_date - as_of).days,
            )
        )
    return meetings


def get_next_meeting(as_of: dt.date | None = None) -> MeetingInfo | None:
    for m in get_meeting_schedule(as_of):
        if m.is_next:
            return m
    return None

@st.cache_data(ttl=3600)
def fetch_fed_funds_rate_history(lookback_days: int = 730) -> pd.DataFrame:
    """
    Pull the effective Federal Funds Rate (FEDFUNDS, daily EFFR series DFF)
    from FRED's public CSV export. Falls back to a small bundled dataset
    if the network call fails so the app never shows a blank chart.
    """
    try:
        url = FRED_SERIES_URL.format(series="DFF")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(pd.io.common.StringIO(resp.text))
        df.columns = ["date", "rate"]
        df["date"] = pd.to_datetime(df["date"])
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        df = df.dropna().sort_values("date")
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=lookback_days)
        return df[df["date"] >= cutoff].reset_index(drop=True)
    except Exception:
        df = FALLBACK_RATE_HISTORY.copy()
        df = df.rename(columns={"rate_upper": "rate"})
        return df


def get_last_completed_meeting(as_of: dt.date | None = None) -> MeetingInfo | None:
    """Return the most recent FOMC meeting that has already concluded."""
    as_of = as_of or dt.date.today()
    past = [m for m in get_meeting_schedule(as_of) if m.end <= as_of]
    return past[-1] if past else None


def fetch_latest_statement_text() -> dict:
    """
    Fetch the FOMC statement for the most recently completed meeting directly
    from federalreserve.gov, using the site's predictable URL pattern:
    /newsevents/pressreleases/monetary{YYYYMMDD}a.htm (date = second meeting day).

    Returns a dict with 'text', 'url', and 'meeting_date', or raises ValueError
    with a friendly message if the fetch or parsing fails (e.g. layout change,
    no network, or the release simply isn't published yet).
    """
    from bs4 import BeautifulSoup

    meeting = get_last_completed_meeting()
    if meeting is None:
        raise ValueError("Belum ada rapat FOMC yang selesai pada kalender ini.")

    url = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{meeting.end:%Y%m%d}a.htm"

    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FOMCTracker/1.0)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        raise ValueError(
            f"Gagal mengambil statement dari federalreserve.gov: {exc}. "
            "Coba tempel teks statement secara manual sebagai gantinya."
        ) from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    full_text = soup.get_text("\n")

    start_markers = ["approved the following statement", "For release at"]
    end_marker = "For media inquiries"

    start_idx = -1
    for marker in start_markers:
        idx = full_text.find(marker)
        if idx != -1:
            start_idx = idx
            break

    end_idx = full_text.find(end_marker)

    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError(
            "Tidak bisa menemukan teks statement di halaman (struktur situs mungkin berubah). "
            "Coba tempel teks secara manual sebagai gantinya."
        )

    raw_segment = full_text[start_idx:end_idx]
    # Drop the leading marker sentence itself, keep the statement paragraphs.
    lines = [ln.strip() for ln in raw_segment.split("\n") if ln.strip()]
    statement_lines = [ln for ln in lines if not ln.startswith(("approved the following", "For release at"))]
    statement_text = "\n\n".join(statement_lines)

    if len(statement_text) < 80:
        raise ValueError("Teks statement yang berhasil diambil terlalu pendek, kemungkinan parsing gagal.")

    return {
        "text": statement_text,
        "url": url,
        "meeting_date": meeting.end,
    }


def estimate_move_probabilities(current_upper: float = CURRENT_TARGET_RANGE[1]) -> dict:
    """
    Lightweight, CME-FedWatch-style estimate of the market-implied probability
    of a hold / 25bp cut / 25bp hike at the next meeting, derived from 30-Day
    Fed Funds futures (ZQ) pricing via Yahoo Finance.

    Methodology (simplified from the CME FedWatch approach):
    implied rate = 100 - futures_price
    The gap between the implied rate and the current effective rate, scaled
    by the fraction of the month the new rate would be in effect, gives the
    probability-weighted expected rate change.

    If futures data is unavailable, returns a neutral placeholder so the UI
    can still render with a clear "data unavailable" note instead of crashing.
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("ZQ=F")
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError("no futures data returned")
        last_price = float(hist["Close"].dropna().iloc[-1])
        implied_rate = 100 - last_price
        current_mid = (CURRENT_TARGET_RANGE[0] + CURRENT_TARGET_RANGE[1]) / 2
        delta = implied_rate - current_mid

        # Convert the implied delta into rough hold/cut/hike odds.
        # This is a simplified heuristic, not the full CME methodology.
        if delta <= -0.10:
            p_cut = min(0.85, 0.5 + abs(delta) * 2)
            p_hold = 1 - p_cut - 0.03
            p_hike = 0.03
        elif delta >= 0.10:
            p_hike = min(0.85, 0.5 + delta * 2)
            p_hold = 1 - p_hike - 0.03
            p_cut = 0.03
        else:
            p_hold = 0.70
            p_cut = 0.18
            p_hike = 0.12

        total = p_cut + p_hold + p_hike
        return {
            "cut": round(p_cut / total * 100, 1),
            "hold": round(p_hold / total * 100, 1),
            "hike": round(p_hike / total * 100, 1),
            "source": "live",
            "implied_rate": round(implied_rate, 2),
        }
    except Exception:
        return {
            "cut": 18.0,
            "hold": 70.0,
            "hike": 12.0,
            "source": "fallback",
            "implied_rate": None,
        }

#data backtsest
HISTORICAL_FOMC = [
    {"date": "2023-07-26", "action": "hike", "prev_rate": 5.08},
    {"date": "2023-09-20", "action": "hold", "prev_rate": 5.33},
    {"date": "2023-11-01", "action": "hold", "prev_rate": 5.33},
    {"date": "2023-12-13", "action": "hold", "prev_rate": 5.33},
    {"date": "2024-01-31", "action": "hold", "prev_rate": 5.33},
    {"date": "2024-03-20", "action": "hold", "prev_rate": 5.33},
    {"date": "2024-05-01", "action": "hold", "prev_rate": 5.33},
    {"date": "2024-06-12", "action": "hold", "prev_rate": 5.33},
]

def run_fomc_backtest():
    """
    Menjalankan backtest dengan membandingkan harga ZQ=F H-1 
    dengan keputusan asli The Fed.
    """
    results = []
    correct_predictions = 0

    for meeting in HISTORICAL_FOMC:
        target_date = dt.datetime.strptime(meeting["date"], "%Y-%m-%d").date()
        
        # Ambil harga ZQ=F H-1 (satu hari sebelum rapat)
        h_minus_1 = target_date - dt.timedelta(days=1)
        start_fetch = h_minus_1 - dt.timedelta(days=4)
        
        try:
            
            ticker = yf.Ticker("ZQ=F")
            df = ticker.history(start=start_fetch, end=target_date)
            
            if df.empty:
                continue

                
            last_price = df['Close'].iloc[-1]
            implied_rate = 100 - last_price
            
        
            rate_diff = implied_rate - meeting["prev_rate"]
            
            if rate_diff > 0.03:
                market_prediction = "hike"
            elif rate_diff < -0.03:
                market_prediction = "cut"
            else:
                market_prediction = "hold"
                
            is_correct = market_prediction == meeting["action"]
            if is_correct:
                correct_predictions += 1
                
            results.append({
                "Tanggal Rapat": meeting["date"],
                "Harga ZQ=F (H-1)": round(last_price, 3),
                "Implied Rate": f"{round(implied_rate, 3)}%",
                "Prediksi Pasar": market_prediction.upper(),
                "Keputusan Asli": meeting["action"].upper(),
                "Status": "✅ Akurat" if is_correct else "❌ Meleset"
            })
            
        except Exception:
            continue
            
    accuracy = (correct_predictions / len(results)) * 100 if results else 0
    return pd.DataFrame(results), accuracy

@st.cache_data(ttl=3600)        
def fetch_correlation_data(lookback_days=180):

    tickers = {
        "S&P 500": "^GSPC",
        "Bitcoin": "BTC-USD",
        "Emas": "GC=F",
        "DXY (USD)": "DX-Y.NYB",
        "Minyak (WTI)": "CL=F"
    }
    
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=lookback_days)
    
    df_list = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date, end=end_date)
            if not hist.empty:
                hist.index = hist.index.tz_localize(None).normalize()
                close_price = hist['Close'].rename(name)
                df_list.append(close_price)
        except Exception:
            continue
            
    if df_list:
        try:
            price_df = pd.concat(df_list, axis=1)
            price_df = price_df.ffill().dropna()
            returns_df = price_df.pct_change().dropna()
            corr_matrix = returns_df.corr()
            return corr_matrix
        except Exception:
            return pd.DataFrame()
            
    return pd.DataFrame()