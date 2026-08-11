from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import requests
import streamlit as st

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"
FINNHUB_CATEGORIES = {
    "general": "Umum",
    "forex": "Forex",
    "crypto": "Kripto",
}
CATEGORY_KEYWORDS = {
    "Bank Sentral": [
        "fed", "fomc", "federal reserve", "powell", "ecb", "bank of england",
        "boe", "bank of japan", "boj", "interest rate", "rate cut", "rate hike",
        "central bank", "monetary policy",
    ],
    "Data Makro (CPI/PPI)": [
        "inflation", "cpi", "ppi", "pce", "consumer price", "producer price", 
        "gdp", "nfp", "payroll", "jobless claims", "labor market", "employment", 
        "retail sales", "economic growth", "makro"
    ],
    "Pasar Saham": ["stocks", "s&p", "nasdaq", "dow jones", "wall street", "equities"],
    "Komoditas": ["oil", "gold", "commodity", "opec", "crude"],
}

ALL_TAGS = ["Semua", "Bank Sentral", "Data Makro (CPI/PPI)", "Pasar Saham", "Kripto", "Forex", "Komoditas", "Umum"]


@dataclass
class NewsItem:
    headline: str
    summary: str
    source: str
    url: str
    datetime: dt.datetime
    image: str | None
    tags: list[str]


@dataclass
class FetchDiagnostics:
    """Per-category fetch results, so the UI can explain empty filters."""
    counts: dict = field(default_factory=dict)  
    errors: dict = field(default_factory=dict)  


def _keyword_tags(headline: str, summary: str) -> list[str]:
    text = f"{headline} {summary}".lower()
    return [cat for cat, kws in CATEGORY_KEYWORDS.items() if any(kw in text for kw in kws)]


def _fetch_one_category(finnhub_category: str, base_tag: str, api_key: str, limit: int) -> list[NewsItem]:
    resp = requests.get(
        FINNHUB_NEWS_URL,
        params={"category": finnhub_category, "token": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    raw_items = resp.json()

    if not isinstance(raw_items, list):
        raise ValueError(f"Respons tidak terduga dari Finnhub: {raw_items}")

    items = []
    for raw in raw_items[:limit]:
        try:
            headline = (raw.get("headline") or "").strip()
            summary = (raw.get("summary") or "").strip()
            if not headline:
                continue
            tags = [base_tag] + _keyword_tags(headline, summary)
            tags = list(dict.fromkeys(tags))  
            items.append(
                NewsItem(
                    headline=headline,
                    summary=summary,
                    source=raw.get("source", "—"),
                    url=raw.get("url", ""),
                    datetime=dt.datetime.fromtimestamp(raw.get("datetime", 0)),
                    image=raw.get("image") or None,
                    tags=tags,
                )
            )
        except Exception:
            continue
    return items

@st.cache_data(ttl=600) 
def fetch_market_news(api_key: str, limit_per_category: int = 25) -> tuple[list[NewsItem], FetchDiagnostics]:
    if not api_key:
        raise ValueError("Finnhub API key belum diisi. Masukkan di sidebar terlebih dahulu.")

    all_items: list[NewsItem] = []
    diag = FetchDiagnostics()

    for finnhub_category, base_tag in FINNHUB_CATEGORIES.items():
        try:
            fetched = _fetch_one_category(finnhub_category, base_tag, api_key, limit_per_category)
            diag.counts[finnhub_category] = len(fetched)
            all_items.extend(fetched)
        except Exception as exc:
            diag.counts[finnhub_category] = 0
            diag.errors[finnhub_category] = str(exc)

    if not all_items:
        detail = "; ".join(f"{k}: {v}" for k, v in diag.errors.items())
        raise ValueError(f"Finnhub tidak mengembalikan data berita sama sekali. Detail: {detail or 'tidak diketahui'}")

    seen = set()
    deduped = []
    for item in all_items:
        if item.url in seen:
            continue
        seen.add(item.url)
        deduped.append(item)

    deduped.sort(key=lambda n: n.datetime, reverse=True)
    return deduped, diag


def filter_by_tag(items: list[NewsItem], tag: str) -> list[NewsItem]:
    if tag == "Semua":
        return items
    return [n for n in items if tag in n.tags]
