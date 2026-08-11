from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests

FED_RSS_URL = "https://www.federalreserve.gov/feeds/press_all.xml"

HAWKISH_WORDS = ["inflation", "tightening", "persistent", "elevated", "restrictive", "higher"]
DOVISH_WORDS = ["cut", "easing", "soft landing", "accommodat", "lower", "support", "stimulus"]


@dataclass
class WireItem:
    title: str
    link: str
    published: dt.datetime | None
    lean: str        
    lean_class: str   


def _guess_lean(title: str) -> tuple[str, str]:
    lower = title.lower()
    hawkish_hits = sum(1 for w in HAWKISH_WORDS if w in lower)
    dovish_hits = sum(1 for w in DOVISH_WORDS if w in lower)
    if hawkish_hits > dovish_hits:
        return "Cenderung Hawkish (kasar)", "hawkish"
    if dovish_hits > hawkish_hits:
        return "Cenderung Dovish (kasar)", "dovish"
    return "Netral / Umum", "neutral"


def fetch_fed_press_wire(limit: int = 8) -> list[WireItem]:
    try:
        resp = requests.get(
            FED_RSS_URL,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MarketPulse/1.0)"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:
        raise ValueError(f"Gagal mengambil RSS feed dari federalreserve.gov: {exc}") from exc

    items = []
    for item in root.findall(".//item")[:limit]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")

        title = title_el.text.strip() if title_el is not None and title_el.text else "Rilis Federal Reserve"
        link = link_el.text.strip() if link_el is not None and link_el.text else "https://www.federalreserve.gov/newsevents/pressreleases.htm"

        published = None
        if pub_el is not None and pub_el.text:
            try:
                published = parsedate_to_datetime(pub_el.text)
            except Exception:
                published = None

        lean, lean_class = _guess_lean(title)
        items.append(WireItem(title=title, link=link, published=published, lean=lean, lean_class=lean_class))

    return items
