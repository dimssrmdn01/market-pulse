import datetime as dt
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from modules import ai_analysis, data, fed_wire, news
from modules.gauge import render_hawk_dove_gauge
from modules import styling
from modules.styling import hex_to_rgba

load_dotenv()

st.set_page_config(
    page_title="Market Pulse",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'ID'

def toggle_lang():
    if st.session_state['lang'] == 'ID':
        st.session_state['lang'] = 'EN'
    else:
        st.session_state['lang'] = 'ID'

lang = st.session_state['lang']

def get_saved_key(name: str) -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, "")

# -------------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<p style='font-family:Fraunces,serif; font-size:1.3rem; color:#F3EEDF; margin-bottom:0;'>Market Pulse</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#9C9478; font-size:0.8rem; margin-top:0;'>Economic & financial markets dashboard</p>",
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    st.markdown(
        f"<p style='font-family:IBM Plex Mono,monospace; font-size:0.72rem; text-transform:uppercase; "
        f"letter-spacing:0.08em; color:#B9975B;'>{'Tampilan' if lang == 'ID' else 'Appearance'}</p>",
        unsafe_allow_html=True,
    )
    theme_key = st.selectbox(
        "Tema Warna",
        options=list(styling.THEMES.keys()),
        format_func=lambda k: styling.THEMES[k]["display_name"],
        label_visibility="collapsed",
    )

theme = styling.inject_css(theme_key)

st.html("""
<style>
    [data-testid="stHeader"] { background-color: transparent !important; }
    .stAppDeployButton { display: none !important; }
    [data-testid="stHeader"] button { color: #F3EEDF !important; }
    [data-testid="stHeader"] button:hover { color: #B9975B !important; }
</style>
""")

with st.sidebar:
    button_label = "🌐 Switch to English" if lang == 'ID' else "🌐 Ganti ke Indonesia"
    st.button(button_label, on_click=toggle_lang, use_container_width=True)
    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)
    st.markdown(
        "<p style='font-family:IBM Plex Mono,monospace; font-size:0.72rem; text-transform:uppercase; "
        "letter-spacing:0.08em; color:#B9975B;'>API Keys</p>",
        unsafe_allow_html=True,
    )

    saved_finnhub_key = get_saved_key("FINNHUB_API_KEY")
    saved_groq_key = get_saved_key("GROQ_API_KEY")

    if saved_finnhub_key:
        finnhub_api_key = saved_finnhub_key
        st.caption("✓ Finnhub API Key dimuat otomatis..." if lang == 'ID' else "✓ Finnhub API Key loaded automatically...")
    else:
        finnhub_api_key = st.text_input("Finnhub API Key", type="password", placeholder="c...")
        st.caption("Dapatkan gratis di [finnhub.io/register](https://finnhub.io/register)untuk tab Ringkasan Pasar." if lang == 'ID' else "Get it for free at [finnhub.io/register](https://finnhub.io/register) — for the Market Overview tab.")

    if saved_groq_key:
        groq_api_key = saved_groq_key
        st.caption("✓ Groq API Key dimuat otomatis..." if lang == 'ID' else "✓ Groq API Key loaded automatically...")
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
        st.caption("Dapatkan gratis di [console.groq.com](https://console.groq.com/keys) untuk analisis sentimen AI." if lang == 'ID' else "Get it for free at [console.groq.com](https://console.groq.com/keys) — for AI sentiment analysis.")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)
    st.markdown(
       f"<p style='font-family:IBM Plex Mono,monospace; font-size:0.72rem; text-transform:uppercase; "
       f"letter-spacing:0.08em; color:#B9975B;'>{'Watchlist Personal' if lang == 'ID' else 'Personal Watchlist'}</p>",
       unsafe_allow_html=True,
    )

    grouped_assets = data.get_assets_grouped()
    default_by_category = {
        "crypto": ["BTC/USD", "ETH/USD"],
        "forex": ["EUR/USD", "USD/IDR"],
        "commodity": ["Emas (Gold)"],
        "stock": ["S&P 500"],
        "idx_stock": ["IHSG (JKSE)", "BCA (BBCA)"],
    }

    selected_assets = []
    for cat in data.CATEGORY_ORDER:
        labels_in_cat = grouped_assets.get(cat, [])
        if not labels_in_cat:
            continue
        cat_label = data.CATEGORY_LABELS[cat][lang]
        with st.expander(cat_label, expanded=(cat in ("crypto", "forex"))):
            picked = st.multiselect(
                cat_label,
                options=labels_in_cat,
                default=[d for d in default_by_category.get(cat, []) if d in labels_in_cat],
                label_visibility="collapsed",
                key=f"watchlist_{cat}",
            )
            selected_assets.extend(picked)

# -------------------------------------------------------------------------
# HERO
# -------------------------------------------------------------------------
today = dt.date.today()
next_meeting = data.get_next_meeting(today)
lower, upper = data.CURRENT_TARGET_RANGE

if lang == 'ID':
    st.markdown("### Ringkasan Pasar · Crypto, Forex & Saham")
else:
    st.markdown("### Market Summary · Crypto, Forex & Equities")

with st.spinner("Mengambil harga terkini..." if lang == 'ID' else "Fetching live prices..."):
    snapshot = data.fetch_market_snapshot(selected_assets)

if snapshot:
    from collections import defaultdict
    grouped_snapshot = defaultdict(list)
    for a in snapshot:
        grouped_snapshot[a["category"]].append(a)

    for cat in data.CATEGORY_ORDER:
        items = grouped_snapshot.get(cat)
        if not items:
            continue
        cat_label = data.CATEGORY_LABELS[cat][lang]
        st.markdown(
            f"<p style='font-family:IBM Plex Mono,monospace; font-size:0.68rem; "
            f"text-transform:uppercase; letter-spacing:0.06em; color:#7A7360; "
            f"margin:0.6rem 0 0.2rem;'>{cat_label}</p>",
            unsafe_allow_html=True,
        )
        ticker_html = "".join(
            f"""
<div class="ticker-item">
    <div class="ticker-symbol">{a['label']}</div>
    <div class="ticker-price">{data.format_price(a['price'], a['category'])}</div>
    <div class="ticker-change {'up' if a['change_pct'] >= 0 else 'down'}">{'+' if a['change_pct'] >= 0 else ''}{a['change_pct']:.2f}%</div>
</div>
"""
            for a in items
        )
        st.markdown(f'<div class="ticker-strip">{ticker_html}</div>', unsafe_allow_html=True)
else:
    st.caption("⚠ Data harga live tidak tersedia saat ini - coba muat ulang halaman." if lang == 'ID' else "⚠ Live price data currently unavailable - try reloading the page.")

hero_col1, hero_col2 = st.columns([2, 1])
with hero_col1:
    if next_meeting and next_meeting.days_away > 0:
        days_label = f"{next_meeting.days_away} hari lagi" if lang == 'ID' else f"{next_meeting.days_away} days away"
    else:
        days_label = "Sedang berlangsung / baru saja selesai" if lang == 'ID' else "In progress / recently concluded"

    eyebrow = "Federal Reserve &middot; Kebijakan Moneter" if lang == 'ID' else "Federal Reserve &middot; Monetary Policy"
    meeting_lbl = "Rapat FOMC berikutnya:" if lang == 'ID' else "Next FOMC meeting:"
    sep_lbl = " &middot; disertai Summary of Economic Projections (dot plot)" if lang == 'ID' else " &middot; includes Summary of Economic Projections (dot plot)"

    st.markdown(
        f"""
<div class="ledger-hero">
    <div class="ledger-eyebrow">{eyebrow}</div>
    <p class="ledger-rate">{lower:.2f}<span class="unit">%</span> &ndash; {upper:.2f}<span class="unit">%</span></p>
    <p class="ledger-sub">
        {meeting_lbl} <strong>{next_meeting.start.strftime('%d %B') if next_meeting else '—'}
        &ndash; {next_meeting.end.strftime('%d %B %Y') if next_meeting else '—'}</strong>
        &middot; {days_label}
        {sep_lbl if next_meeting and next_meeting.has_sep else ""}
    </p>
</div>
""",
        unsafe_allow_html=True,
    )
with hero_col2:
    probs = data.estimate_move_probabilities()
    prob_title = "Probabilitas Pasar &middot; Rapat Berikutnya" if lang == 'ID' else "Market Probabilities &middot; Next Meeting"
    st.markdown(
        f"""
<div class="parchment-card">
    <div class="label">{prob_title}</div>
    <div style="display:flex; justify-content:space-between; margin-top:0.6rem; font-family:'IBM Plex Mono',monospace;">
        <div><div style="color:{theme['info']}; font-weight:600; font-size:1.1rem;">{probs['cut']}%</div><div style="font-size:0.7rem;">CUT</div></div>
        <div><div style="color:#6B6250; font-weight:600; font-size:1.1rem;">{probs['hold']}%</div><div style="font-size:0.7rem;">HOLD</div></div>
        <div><div style="color:{theme['down']}; font-weight:600; font-size:1.1rem;">{probs['hike']}%</div><div style="font-size:0.7rem;">HIKE</div></div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if probs["source"] == "fallback":
        st.caption("⚠ Data futures live tidak tersedia - menampilkan estimasi cadangan." if lang == 'ID' else "⚠ Live futures data unavailable - showing fallback estimates.")

st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

# -------------------------------------------------------------------------
# TABS (regrouped: 4 tabs by user intent instead of 6 by data source)
# -------------------------------------------------------------------------
tab_names = [
    "Ringkasan Pasar" if lang == 'ID' else "Market Overview",
    "Bank Sentral" if lang == 'ID' else "Central Bank",
    "Analisis Kuantitatif" if lang == 'ID' else "Quantitative Analysis",
    "Analisis Statement" if lang == 'ID' else "Statement Analysis",
]
tab_overview, tab_central, tab_quant, tab_ai = st.tabs(tab_names)

# =========================================================================
# TAB 1: RINGKASAN PASAR — AI recap + news feed + news sentiment
# =========================================================================
with tab_overview:
    with st.expander("Analisis Pasar Otomatis (AI)" if lang == 'ID' else "Automated Market Analysis (AI)"):
        st.caption("Buat ringkasan naratif otomatis berdasarkan pergerakan harga dan berita terbaru." if lang == 'ID' else "Generate an automated narrative summary based on latest price actions and news.")

        if st.button("Generate Briefing", type="primary", use_container_width=True):
            if not groq_api_key or not finnhub_api_key:
                st.error("API Key Groq & Finnhub harus diisi di sidebar." if lang == 'ID' else "Groq & Finnhub API Keys must be provided in the sidebar.")
            else:
                try:
                    with st.spinner("AI sedang merangkum pasar..." if lang == 'ID' else "AI is summarizing the market..."):
                        news_items, _ = news.fetch_market_news(finnhub_api_key)
                        headlines = [n.headline for n in news_items] if news_items else ["Tidak ada berita utama."]
                        recap_text = ai_analysis.generate_market_recap(snapshot, headlines, groq_api_key, lang)
                        st.success(recap_text)
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    st.markdown("#### Berita Ekonomi & Pasar Finansial" if lang == 'ID' else "#### Economic & Financial Market News")
    st.caption(
        "Feed berita terkini dari Finnhub, otomatis ditandai per topik. Klik 'Analisis Sentimen Pasar' untuk penilaian AI atas mood pasar secara keseluruhan."
        if lang == 'ID' else
        "Latest news feed from Finnhub, automatically tagged by topic. Click 'Analyze Market Sentiment' for an AI assessment of the overall market mood."
    )

    if not finnhub_api_key:
        st.info("Masukkan Finnhub API key di sidebar untuk memuat berita terkini." if lang == 'ID' else "Enter Finnhub API key in the sidebar to load the latest news.")
    else:
        if "news_items" not in st.session_state:
            st.session_state["news_items"] = None
        if "news_diag" not in st.session_state:
            st.session_state["news_diag"] = None

        col_refresh, col_filter = st.columns([1, 3])
        with col_refresh:
            if st.button("Muat Ulang Berita" if lang == 'ID' else "Reload News"):
                try:
                    with st.spinner("Mengambil berita dari Finnhub..." if lang == 'ID' else "Fetching news from Finnhub..."):
                        items_, diag_ = news.fetch_market_news(finnhub_api_key)
                    st.session_state["news_items"] = items_
                    st.session_state["news_diag"] = diag_
                except ValueError as e:
                    st.error(str(e))

        if st.session_state["news_items"] is None:
            try:
                with st.spinner("Mengambil berita dari Finnhub..." if lang == 'ID' else "Fetching news from Finnhub..."):
                    items_, diag_ = news.fetch_market_news(finnhub_api_key)
                st.session_state["news_items"] = items_
                st.session_state["news_diag"] = diag_
            except ValueError as e:
                st.error(str(e))

        items = st.session_state["news_items"]
        diag = st.session_state["news_diag"]

        if diag is not None:
            with st.expander("Detail sumber data" if lang == 'ID' else "Data source details"):
                for cat, count in diag.counts.items():
                    if cat in diag.errors:
                        st.caption(f"⚠ `{cat}`: gagal — {diag.errors[cat]}" if lang == 'ID' else f"⚠ `{cat}`: failed — {diag.errors[cat]}")
                    else:
                        st.caption(f"✓ `{cat}`: {count} artikel" if lang == 'ID' else f"✓ `{cat}`: {count} articles")

        if items:
            with col_filter:
                tag_translations = {
                    "Semua": "All", "Bank Sentral": "Central Banks", "Data Makro (CPI/PPI)": "Macro Data (CPI/PPI)",
                    "Pasar Saham": "Equities", "Kripto": "Crypto", "Forex": "Forex", "Komoditas": "Commodities"
                }
                selected_tag = st.radio(
                    "Filter topik", news.ALL_TAGS, horizontal=True, label_visibility="collapsed",
                    format_func=lambda x: x if lang == 'ID' else tag_translations.get(x, x)
                )
            filtered = news.filter_by_tag(items, selected_tag)

            if st.button("Analisis Sentimen Pasar" if lang == 'ID' else "Analyze Market Sentiment", type="primary"):
                if not groq_api_key:
                    st.error("Masukkan Groq API Key di sidebar terlebih dahulu." if lang == 'ID' else "Please enter your Groq API Key in the sidebar first.")
                elif not filtered:
                    st.error("Tidak ada berita pada kategori ini untuk dianalisis." if lang == 'ID' else "No news in this category to analyze.")
                else:
                    try:
                        with st.spinner("Menganalisis mood pasar..." if lang == 'ID' else "Analyzing market mood..."):
                            headlines = [n.headline for n in filtered[:40]]
                            result = ai_analysis.analyze_news_sentiment(headlines, groq_api_key)
                        st.session_state["news_sentiment"] = result
                    except ValueError as e:
                        st.error(str(e))

            if "news_sentiment" in st.session_state:
                result = st.session_state["news_sentiment"]
                col_gauge, col_detail = st.columns([1, 1.3])
                with col_gauge:
                    st.markdown(
                        render_hawk_dove_gauge(
                            result["score"], result["label"],
                            left_label="BEARISH", right_label="BULLISH", theme=theme,
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="gauge-caption">{"Skor Sentimen Pasar" if lang == "ID" else "Market Sentiment Score"}</div>', unsafe_allow_html=True)
                with col_detail:
                    st.markdown(
                        f"""
<div class="parchment-card">
    <div class="label">{"Ringkasan" if lang == "ID" else "Summary"}</div>
    <p style="margin-top:0.5rem; line-height:1.5;">{result['summary']}</p>
    <div class="label" style="margin-top:1rem;">{"Frasa Kunci" if lang == "ID" else "Key Phrases"}</div>
    <ul style="margin-top:0.4rem;">
        {''.join(f'<li>{p}</li>' for p in result['key_phrases'])}
    </ul>
</div>
""",
                        unsafe_allow_html=True,
                    )
                st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

            st.markdown("##### Feed Berita" if lang == 'ID' else "##### News Feed")
            if not filtered:
                cat_error = diag.errors.get({"Kripto": "crypto", "Forex": "forex"}.get(selected_tag, ""), None) if diag else None
                if cat_error:
                    st.warning(f"Gagal mengambil berita kategori '{selected_tag}' dari Finnhub: {cat_error}" if lang == 'ID' else f"Failed to fetch '{selected_tag}' news from Finnhub: {cat_error}")
                else:
                    st.info(f"Belum ada berita untuk kategori '{selected_tag}' saat ini." if lang == 'ID' else f"No news available for the '{selected_tag}' category at this time.")
            for n in filtered:
                tags_html = "".join(f'<span class="news-tag">{tag_translations.get(t, t) if lang == "EN" else t}</span>' for t in n.tags)
                st.markdown(
                    f"""
<div class="news-card">
    <div class="news-meta">{n.source} &middot; {n.datetime.strftime('%d %b %Y, %H:%M')}</div>
    <p class="news-headline"><a href="{n.url}" target="_blank">{n.headline}</a></p>
    <div>{tags_html}</div>
    {f'<p class="news-summary">{n.summary}</p>' if n.summary else ''}
</div>
""",
                    unsafe_allow_html=True,
                )
        elif items is not None:
            st.info("Belum ada berita untuk ditampilkan." if lang == 'ID' else "No news to display.")

# =========================================================================
# TAB 2: BANK SENTRAL — FOMC calendar + CPI/NFP + Fed Wire, one place
# =========================================================================
with tab_central:
    st.markdown("#### Jadwal Rapat FOMC 2026" if lang == 'ID' else "#### 2026 FOMC Meeting Schedule")
    schedule = data.get_meeting_schedule(today)
    for m in schedule:
        css_class = "meeting-row is-next" if m.is_next else "meeting-row"
        status = ("→ RAPAT BERIKUTNYA" if lang == 'ID' else "→ NEXT MEETING") if m.is_next else (("selesai" if lang == 'ID' else "completed") if m.end < today else "")
        sep_tag = '<span class="meeting-tag">SEP + Dot Plot</span>' if m.has_sep else ""

        st.html(
            f"""
<div class="{css_class}">
    <div class="meeting-date">{m.start.strftime('%d %b')} &ndash; {m.end.strftime('%d %b %Y')}</div>
    {sep_tag}
    <div style="margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:0.75rem; color:{theme['accent'] if m.is_next else theme['sidebar_label']};">{status}</div>
</div>
"""
        )
    st.caption("Empat dari delapan rapat (Maret, Juni, September, Desember) disertai Summary of Economic Projections (dot plot)." if lang == 'ID' else "Four out of eight meetings (March, June, September, December) include a Summary of Economic Projections (dot plot).")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    col_cpi, col_nfp = st.columns(2)
    with col_cpi:
        st.markdown("##### Jadwal Rilis CPI (Inflasi)" if lang == 'ID' else "##### CPI (Inflation) Release Schedule")
        cpi_schedule = data.get_release_schedule(data.CPI_CALENDAR_2026, today)
        for r in cpi_schedule:
            if r.days_away < -3:
                continue
            css_class = "meeting-row is-next" if r.is_next else "meeting-row"
            status = ("→ BERIKUTNYA" if lang == 'ID' else "→ NEXT") if r.is_next else (("selesai" if lang == 'ID' else "completed") if r.release_date < today else "")
            st.html(
                f"""
<div class="{css_class}">
    <div class="meeting-date">{r.release_date.strftime('%d %b %Y')}</div>
    <div style="font-size:0.75rem; color:{theme['sidebar_label']};">Data {r.reference_month}</div>
    <div style="margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; color:{theme['accent'] if r.is_next else theme['sidebar_label']};">{status}</div>
</div>
"""
            )
        st.caption("Sumber: U.S. Bureau of Labor Statistics." if lang == 'ID' else "Source: U.S. Bureau of Labor Statistics.")

    with col_nfp:
        st.markdown("##### Jadwal Rilis NFP (Employment Situation)" if lang == 'ID' else "##### NFP (Employment) Release Schedule")
        nfp_schedule = data.get_release_schedule(data.NFP_CALENDAR_2026, today)
        for r in nfp_schedule:
            if r.days_away < -3:
                continue
            css_class = "meeting-row is-next" if r.is_next else "meeting-row"
            status = ("→ BERIKUTNYA" if lang == 'ID' else "→ NEXT") if r.is_next else (("selesai" if lang == 'ID' else "completed") if r.release_date < today else "")
            st.html(
                f"""
<div class="{css_class}">
    <div class="meeting-date">{r.release_date.strftime('%d %b %Y')}</div>
    <div style="font-size:0.75rem; color:{theme['sidebar_label']};">Data {r.reference_month}</div>
    <div style="margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; color:{theme['accent'] if r.is_next else theme['sidebar_label']};">{status}</div>
</div>
"""
            )
        st.caption("Sumber: U.S. Bureau of Labor Statistics." if lang == 'ID' else "Source: U.S. Bureau of Labor Statistics.")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    st.markdown("#### Fed Wire &middot; Rilis Resmi federalreserve.gov" if lang == 'ID' else "#### Fed Wire &middot; Official Releases federalreserve.gov")
    st.caption(
        "Feed RSS resmi rilis pers Federal Reserve. Tag Hawkish/Dovish di sini murni hitungan kata kunci sederhana pada judul, bukan model NLP atau analisis mendalam. Untuk penilaian AI yang sesungguhnya atas teks statement, pakai tab 'Analisis Statement'."
        if lang == 'ID' else
        "Official RSS feed for Federal Reserve press releases. Hawkish/Dovish tags here are purely basic keyword counts on titles — not an NLP model or deep analysis. For true AI assessment, use the 'Statement Analysis' tab."
    )

    if st.button("Muat Ulang Fed Wire" if lang == 'ID' else "Reload Fed Wire"):
        st.session_state.pop("fed_wire_items", None)

    if "fed_wire_items" not in st.session_state:
        try:
            with st.spinner("Mengambil RSS feed dari federalreserve.gov..." if lang == 'ID' else "Fetching RSS feed from federalreserve.gov..."):
                st.session_state["fed_wire_items"] = fed_wire.fetch_fed_press_wire()
        except ValueError as e:
            st.session_state["fed_wire_items"] = None
            st.error(str(e))

    wire_items = st.session_state.get("fed_wire_items")
    if wire_items:
        for w in wire_items:
            time_str = w.published.strftime("%d %b %Y, %H:%M") if w.published else "—"
            st.markdown(
                f"""
<div class="wire-row">
    <p class="wire-title"><a href="{w.link}" target="_blank">{w.title}</a></p>
    <div class="wire-meta">{time_str}</div>
    <span class="wire-lean {w.lean_class}">{w.lean}</span>
</div>
""",
                unsafe_allow_html=True,
            )
    elif wire_items is not None:
        st.info("Belum ada rilis untuk ditampilkan." if lang == 'ID' else "No releases to display.")

# =========================================================================
# TAB 3: ANALISIS KUANTITATIF — Rate history + backtest + correlation
# =========================================================================
with tab_quant:
    st.markdown("#### Riwayat Effective Federal Funds Rate" if lang == 'ID' else "#### Effective Federal Funds Rate History")
    with st.spinner("Mengambil data dari FRED..." if lang == 'ID' else "Fetching data from FRED..."):
        rate_df = data.fetch_fed_funds_rate_history(lookback_days=730)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rate_df["date"],
            y=rate_df["rate"],
            mode="lines",
            line=dict(color=theme["accent"], width=2.5),
            fill="tozeroy",
            fillcolor=hex_to_rgba(theme["accent"], 0.10),
            name="Effective Fed Funds Rate",
        )
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["text"], family="Inter"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=380,
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="Rate (%)"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Sumber: FRED series DFF (Effective Federal Funds Rate), Federal Reserve Bank of St. Louis." if lang == 'ID' else "Source: FRED series DFF (Effective Federal Funds Rate), Federal Reserve Bank of St. Louis.")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    st.markdown("#### Backtest Akurasi Pasar (Fed Funds Futures)" if lang == 'ID' else "#### Market Accuracy Backtest (Fed Funds Futures)")
    st.caption(
        "Mengevaluasi seberapa akurat tebakan pasar (menggunakan harga penutupan instrumen ZQ=F satu hari sebelum rapat) dibandingkan dengan keputusan suku bunga aktual yang diambil oleh FOMC."
        if lang == 'ID' else
        "Evaluates how accurately the market guessed (using ZQ=F closing prices one day prior to the meeting) compared to the actual interest rate decision taken by the FOMC."
    )

    if st.button("Jalankan Backtest Historis" if lang == 'ID' else "Run Historical Backtest"):
        with st.spinner("Menarik data historis dari Yahoo Finance dan menghitung akurasi..." if lang == 'ID' else "Fetching historical data from Yahoo Finance and calculating accuracy..."):
            bt_df, bt_accuracy = data.run_fomc_backtest()

            if not bt_df.empty:
                col_acc, col_space = st.columns([1, 3])
                with col_acc:
                    st.markdown(
                        f"""
                        <div class="parchment-card" style="text-align: center;">
                            <div class="label">{"Akurasi Historis Pasar" if lang == 'ID' else "Market Historical Accuracy"}</div>
                            <div style="color:{theme['info']}; font-size:2rem; font-weight:700;">
                                {bt_accuracy:.1f}%
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown("<br>", unsafe_allow_html=True)
                st.dataframe(
                    bt_df,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.error("Gagal mengambil data historis untuk backtest." if lang == 'ID' else "Failed to fetch historical data for backtest.")

    st.markdown('<hr class="divider-line">', unsafe_allow_html=True)

    st.markdown("#### Matriks Korelasi Aset Makro (Heatmap)" if lang == 'ID' else "#### Macro Asset Correlation Matrix (Heatmap)")
    st.caption(
        "Menganalisis korelasi pergerakan harian (daily returns) antar instrumen utama selama 6 bulan terakhir. Nilai mendekati +1 berarti bergerak searah (korelasi positif kuat), sedangkan mendekati -1 berlawanan arah (korelasi negatif)."
        if lang == 'ID' else
        "Analyzes the correlation of daily returns among major instruments over the last 6 months. A value near +1 indicates moving in the same direction (strong positive correlation), while near -1 indicates opposite directions (negative correlation)."
    )

    with st.spinner("Menghitung matriks korelasi dari Yahoo Finance..." if lang == 'ID' else "Calculating correlation matrix from Yahoo Finance..."):
        corr_matrix = data.fetch_correlation_data(lookback_days=180)

    if not corr_matrix.empty:
        fig_corr = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            colorscale="RdBu",
            zmid=0,
            zmin=-1, zmax=1,
            texttemplate="%{z:.2f}",
            hoverinfo="x+y+z",
            showscale=True
        ))

        fig_corr.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=theme["text"], family="Inter"),
            margin=dict(l=10, r=10, t=30, b=10),
            height=450,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False, autorange="reversed")
        )

        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.error("Gagal mengambil data untuk matriks korelasi." if lang == 'ID' else "Failed to fetch data for the correlation matrix.")

# =========================================================================
# TAB 4: ANALISIS STATEMENT — unchanged, kept as its own interactive flow
# =========================================================================
with tab_ai:
    st.markdown("#### Analisis Sentimen Hawkish / Dovish" if lang == 'ID' else "#### Hawkish / Dovish Sentiment Analysis")
    st.caption(
        "Tempel teks statement FOMC (atau bagian pidato Chair), atau ambil otomatis rilis resmi terakhir. AI akan menilai kecenderungan kebijakan pada skala -100 (sangat dovish) sampai +100 (sangat hawkish)."
        if lang == 'ID' else
        "Paste FOMC statement text (or a portion of the Chair's speech), or fetch the latest official release automatically. AI will score the policy bias on a scale from -100 (highly dovish) to +100 (highly hawkish)."
    )

    src_opts = ["Ambil otomatis dari federalreserve.gov", "Tempel manual", "Contoh statement (Juli 2026)"]
    src_opts_en = ["Fetch automatically from federalreserve.gov", "Paste manually", "Sample statement (July 2026)"]

    source_choice = st.radio(
        "Sumber teks" if lang == 'ID' else "Text source",
        src_opts,
        horizontal=True,
        format_func=lambda x: x if lang == 'ID' else src_opts_en[src_opts.index(x)]
    )

    if "statement_buffer" not in st.session_state:
        st.session_state["statement_buffer"] = ""

    if source_choice == src_opts[0]:
        if st.button("Ambil Statement Terbaru" if lang == 'ID' else "Fetch Latest Statement"):
            try:
                with st.spinner("Mengambil rilis resmi dari federalreserve.gov..." if lang == 'ID' else "Fetching official release from federalreserve.gov..."):
                    fetched = data.fetch_latest_statement_text()
                st.session_state["statement_buffer"] = fetched["text"]
                msg = f"Berhasil diambil — rilis rapat {fetched['meeting_date'].strftime('%d %B %Y')}. [Lihat sumber]({fetched['url']})" if lang == 'ID' else f"Successfully fetched — meeting release {fetched['meeting_date'].strftime('%d %B %Y')}. [View source]({fetched['url']})"
                st.success(msg)
            except ValueError as e:
                st.error(str(e))
        statement_text = st.text_area("Teks Statement FOMC" if lang == 'ID' else "FOMC Statement Text", value=st.session_state["statement_buffer"], height=200)
    elif source_choice == src_opts[2]:
        statement_text = st.text_area("Teks Statement FOMC" if lang == 'ID' else "FOMC Statement Text", value=ai_analysis.SAMPLE_STATEMENT, height=200)
    else:
        statement_text = st.text_area(
            "Teks Statement FOMC" if lang == 'ID' else "FOMC Statement Text", value="", height=200,
            placeholder="Tempel teks statement di sini..." if lang == 'ID' else "Paste statement text here..."
        )

    analyze_clicked = st.button("Analisis Sekarang" if lang == 'ID' else "Analyze Now", type="primary")

    if "analysis_history" not in st.session_state:
        st.session_state["analysis_history"] = []

    if analyze_clicked:
        if not groq_api_key:
            st.error("Masukkan Groq API Key di sidebar terlebih dahulu." if lang == 'ID' else "Please enter your Groq API Key in the sidebar first.")
        else:
            try:
                with st.spinner("Menganalisis nada kebijakan..." if lang == 'ID' else "Analyzing policy tone..."):
                    result = ai_analysis.analyze_statement(statement_text, groq_api_key)
                st.session_state["last_analysis"] = result
                st.session_state["analysis_history"].append(
                    {
                        "waktu": dt.datetime.now().strftime("%H:%M:%S"),
                        "score": result["score"],
                        "label": result["label"],
                    }
                )
            except ValueError as e:
                st.error(str(e))

    if "last_analysis" in st.session_state:
        result = st.session_state["last_analysis"]
        col_gauge, col_detail = st.columns([1, 1.3])
        with col_gauge:
            st.markdown(
                render_hawk_dove_gauge(result["score"], result["label"], theme=theme),
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="gauge-caption">{"Skor Sentimen Kebijakan" if lang == "ID" else "Policy Sentiment Score"}</div>', unsafe_allow_html=True)
        with col_detail:
            st.markdown(
                f"""
<div class="parchment-card">
    <div class="label">{"Ringkasan" if lang == "ID" else "Summary"}</div>
    <p style="margin-top:0.5rem; line-height:1.5;">{result['summary']}</p>
    <div class="label" style="margin-top:1rem;">{"Frasa Kunci" if lang == "ID" else "Key Phrases"}</div>
    <ul style="margin-top:0.4rem;">
        {''.join(f'<li>{p}</li>' for p in result['key_phrases'])}
    </ul>
</div>
""",
                unsafe_allow_html=True,
            )

    if len(st.session_state["analysis_history"]) > 1:
        st.markdown('<hr class="divider-line">', unsafe_allow_html=True)
        st.markdown("##### Tren Skor Sentimen (sesi ini)" if lang == 'ID' else "##### Sentiment Score Trend (this session)")
        hist_df = pd.DataFrame(st.session_state["analysis_history"])
        fig_hist = go.Figure()
        fig_hist.add_trace(
            go.Scatter(
                x=list(range(1, len(hist_df) + 1)),
                y=hist_df["score"],
                mode="lines+markers+text",
                text=hist_df["label"],
                textposition="top center",
                line=dict(color=theme["accent"], width=2),
                marker=dict(size=9, color=theme["accent"]),
            )
        )
        fig_hist.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.25)")
        fig_hist.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=theme["text"], family="Inter"),
            margin=dict(l=10, r=10, t=30, b=10),
            height=280,
            yaxis=dict(range=[-105, 105], title="Skor" if lang == 'ID' else "Score", gridcolor="rgba(255,255,255,0.08)"),
            xaxis=dict(title="Urutan analisis dalam sesi ini" if lang == 'ID' else "Analysis order in this session", dtick=1),
        )
        st.plotly_chart(fig_hist, use_container_width=True)
        st.caption("Riwayat ini hanya tersimpan selama sesi browser aktif dan akan hilang saat halaman di-refresh." if lang == 'ID' else "This history is only saved during the active browser session and will be lost upon refresh.")

# -------------------------------------------------------------------------
# FOOTER
# -------------------------------------------------------------------------
st.markdown('<hr class="divider-line">', unsafe_allow_html=True)
st.caption(
    "Market Pulse adalah proyek edukasi dan portofolio. Data pasar dan estimasi probabilitas bersifat indikatif, bukan nasihat investasi. Selalu verifikasi keputusan kebijakan resmi di federalreserve.gov."
    if lang == 'ID' else
    "Market Pulse is an educational and portfolio project. Market data and probability estimates are indicative, not investment advice. Always verify official policy decisions at federalreserve.gov."
)