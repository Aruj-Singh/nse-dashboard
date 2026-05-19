"""
NSE Trading Dashboard — Zerodha/Kite-inspired dark UI
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="NSE Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent / "data"

# ── Design tokens (Zerodha Kite-inspired) ─────────────────────────────────────
BG       = "#0f0f0f"
SURFACE  = "#1a1a2e"
SURFACE2 = "#16213e"
BORDER   = "rgba(255,255,255,0.07)"
GREEN    = "#22ab94"
RED      = "#eb5757"
BLUE     = "#5086ea"
YELLOW   = "#f7ba50"
TEXT     = "#e0e3eb"
MUTED    = "#636b7a"
WHITE    = "#ffffff"

# plotly rgba equivalents
GREEN_A  = "rgba(34,171,148,0.12)"
RED_A    = "rgba(235,87,87,0.12)"
BLUE_A   = "rgba(80,134,234,0.12)"

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  }}
  .stApp {{ background-color: {BG}; }}
  .block-container {{ padding: 1.2rem 2.5rem 3rem; max-width: 1600px; }}

  /* ── Mood banner ── */
  .mood-banner {{
    border-radius: 14px;
    padding: 1.5rem 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-bottom: 0.5rem;
    border: 1px solid {BORDER};
  }}
  .mood-score {{
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -2px;
  }}
  .mood-label {{
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    margin-bottom: 0.2rem;
  }}
  .mood-advice {{
    font-size: 0.88rem;
    color: {MUTED};
    line-height: 1.5;
  }}
  .mood-factors {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-left: auto;
  }}
  .factor-pill {{
    background: rgba(255,255,255,0.05);
    border: 1px solid {BORDER};
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.72rem;
    font-weight: 500;
    color: {TEXT};
    display: flex;
    align-items: center;
    gap: 5px;
  }}

  /* ── Section header ── */
  .sec-head {{
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {MUTED};
    margin: 1.6rem 0 0.8rem;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .sec-head::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: {BORDER};
  }}

  /* ── Stat card ── */
  .stat-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 1rem 1.2rem;
  }}
  .stat-label {{
    font-size: 0.68rem;
    color: {MUTED};
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
  }}
  .stat-value {{
    font-size: 1.55rem;
    font-weight: 700;
    color: {WHITE};
    line-height: 1.1;
  }}
  .stat-sub {{
    font-size: 0.72rem;
    color: {MUTED};
    margin-top: 0.25rem;
  }}
  .up   {{ color: {GREEN}; }}
  .down {{ color: {RED}; }}
  .flat {{ color: {YELLOW}; }}

  /* ── Signal badge ── */
  .badge-bull   {{ background:{GREEN}22; color:{GREEN}; border:1px solid {GREEN}44; border-radius:4px; padding:2px 9px; font-size:0.68rem; font-weight:700; letter-spacing:.06em; }}
  .badge-bear   {{ background:{RED}22;   color:{RED};   border:1px solid {RED}44;   border-radius:4px; padding:2px 9px; font-size:0.68rem; font-weight:700; }}
  .badge-flat   {{ background:{YELLOW}22; color:{YELLOW}; border:1px solid {YELLOW}44; border-radius:4px; padding:2px 9px; font-size:0.68rem; font-weight:700; }}

  /* ── Interpretation box ── */
  .interp {{
    background: {SURFACE2};
    border-left: 3px solid {BLUE};
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    font-size: 0.8rem;
    color: {TEXT};
    line-height: 1.6;
    margin: 0.6rem 0;
  }}

  /* ── Table ── */
  .stDataFrame {{ border-radius: 8px !important; }}
  [data-testid="stDataFrameResizable"] {{ border: 1px solid {BORDER} !important; border-radius:8px; }}

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {{ background: #0a0a0a; }}

  /* Hide streamlit branding */
  #MainMenu, footer, header {{ visibility: hidden; }}
  .stDeployButton {{ display: none; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load(name: str) -> pd.DataFrame | None:
    p = DATA_DIR / f"{name}.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        return df if not df.empty else None
    except Exception:
        return None

def load_meta() -> dict:
    p = DATA_DIR / "meta.json"
    return json.loads(p.read_text()) if p.exists() else {}

def sec(title: str, icon: str = ""):
    st.markdown(f'<div class="sec-head">{icon}&nbsp;{title}</div>', unsafe_allow_html=True)

def interp(text: str):
    st.markdown(f'<div class="interp">💡 {text}</div>', unsafe_allow_html=True)

def no_data(msg="Fetch pending — click Refresh or wait for auto-fetch."):
    st.markdown(f'<div style="color:{MUTED};font-size:0.8rem;padding:0.5rem 0">{msg}</div>',
                unsafe_allow_html=True)

def plo_layout(fig, title="", height=300, show_legend=True):
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT), x=0),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=TEXT, family="Inter, sans-serif", size=11),
        height=height,
        margin=dict(l=8, r=8, t=36 if title else 8, b=8),
        legend=dict(bgcolor=SURFACE, bordercolor=BORDER, font=dict(size=11)) if show_legend else dict(visible=False),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10)),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10)),
        hovermode="x unified",
    )
    return fig

def stat_card(label, value, sub="", color=WHITE):
    return f"""
    <div class="stat-card">
      <div class="stat-label">{label}</div>
      <div class="stat-value" style="color:{color}">{value}</div>
      {"<div class='stat-sub'>" + sub + "</div>" if sub else ""}
    </div>"""

def fmt_cr(v):
    try:
        f = float(v)
        sign = "+" if f > 0 else ""
        return f"{sign}₹{abs(f):,.0f} Cr"
    except Exception:
        return str(v)


# ── Zone detection + reversal markers ────────────────────────────────────────

def detect_zones(df: pd.DataFrame, tolerance_pct: float = 0.8,
                 cols: dict | None = None, window: int = 4) -> list[dict]:
    """
    Demand/supply zones from swing highs/lows.
    Also records which candle dates touched each zone and whether price reversed.

    `cols` overrides default column names (used for 1H data which has lowercase columns).
    `window` is the swing detection window — use larger for higher-frequency data.
    """
    cols = cols or {"open": "OPEN_INDEX_VAL", "high": "HIGH_INDEX_VAL",
                    "low": "LOW_INDEX_VAL", "close": "CLOSE_INDEX_VAL", "date": "TIMESTAMP"}
    opens  = df[cols["open"]].values
    highs  = df[cols["high"]].values
    lows   = df[cols["low"]].values
    closes = df[cols["close"]].values
    dates  = df[cols["date"]].values
    n = len(df)

    # Find swing highs and lows
    swing_high_idx, swing_low_idx = [], []
    for i in range(window, n - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            swing_high_idx.append(i)
        if lows[i] == min(lows[i-window:i+window+1]):
            swing_low_idx.append(i)

    def cluster_with_dates(indices, price_fn, tol):
        if not indices:
            return []
        pts = sorted([(price_fn(i), i) for i in indices], key=lambda x: x[0])
        zones = []
        group_prices = [pts[0][0]]
        group_idx    = [pts[0][1]]
        for price, idx in pts[1:]:
            if (price - group_prices[0]) / group_prices[0] * 100 <= tol:
                group_prices.append(price)
                group_idx.append(idx)
            else:
                if len(group_prices) >= 2:
                    zones.append({
                        "low":     min(group_prices),
                        "high":    max(group_prices),
                        "touches": len(group_prices),
                        "touch_dates": [dates[i] for i in group_idx],
                        "touch_prices": group_prices,
                    })
                group_prices = [price]
                group_idx    = [idx]
        if len(group_prices) >= 2:
            zones.append({
                "low":     min(group_prices),
                "high":    max(group_prices),
                "touches": len(group_prices),
                "touch_dates": [dates[i] for i in group_idx],
                "touch_prices": group_prices,
            })
        return zones

    supply_zones = [dict(z, type="supply") for z in cluster_with_dates(swing_high_idx, lambda i: highs[i],  tol=tolerance_pct)]
    demand_zones = [dict(z, type="demand") for z in cluster_with_dates(swing_low_idx,  lambda i: lows[i],   tol=tolerance_pct)]

    # Find reversal candles: for each zone, find subsequent bars where price entered zone and closed back out
    def find_reversals(zones, is_demand: bool):
        for z in zones:
            reversals = []  # (date, price) of reversal candle
            for i in range(n):
                in_zone = (lows[i] <= z["high"] and highs[i] >= z["low"])
                if not in_zone:
                    continue
                # Demand: reversal = price dipped into zone but closed above it bullishly
                if is_demand and closes[i] > opens[i] and closes[i] > z["high"] * 0.995:
                    reversals.append({"date": dates[i], "price": lows[i], "close": closes[i]})
                # Supply: reversal = price spiked into zone but closed below it bearishly
                elif not is_demand and closes[i] < opens[i] and closes[i] < z["low"] * 1.005:
                    reversals.append({"date": dates[i], "price": highs[i], "close": closes[i]})
            z["reversals"] = reversals
        return zones

    supply_zones = find_reversals(supply_zones, is_demand=False)
    demand_zones = find_reversals(demand_zones, is_demand=True)

    current_price = closes[-1] if n > 0 else 0
    all_zones = supply_zones + demand_zones
    # Show zones within 10% of current price
    relevant = [z for z in all_zones
                if abs((z["low"] + z["high"]) / 2 - current_price) / current_price < 0.10]
    return sorted(relevant, key=lambda z: (z["touches"], len(z.get("reversals", []))), reverse=True)


# ── Intraday signal detectors ────────────────────────────────────────────────
#
# All detectors return signals in a UNIFIED format:
#   {dt, side ("buy"|"sell"), category, label, key_level,
#    open, high, low, close, body_ratio, ret_2h, ret_4h, ret_8h}
#

def _fwd_returns(closes, i, c):
    def fr(k):
        j = i + k
        return round((closes[j] - c) / c * 100, 2) if j < len(closes) else None
    return fr(1), fr(2), fr(4)


def detect_zone_touch_signals(df: pd.DataFrame, zones: list[dict],
                               zone_tol: float = 0.008,
                               body_ratio: float = 0.35) -> list[dict]:
    """Zone-touch reversal: candle pokes into a zone and closes against it with body ≥ body_ratio."""
    signals = []
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    closes = df["close"].values
    dts    = df["dt"].values

    for i in range(len(df)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        rng = h - l
        if rng == 0 or abs(c - o) / rng < body_ratio:
            continue

        bullish = c > o
        hit_zone = None
        side = None
        for z in zones:
            z_lo = z["low"]  * (1 - zone_tol)
            z_hi = z["high"] * (1 + zone_tol)
            if z["type"] == "demand" and bullish and z_lo <= l <= z_hi:
                hit_zone = z; side = "buy"; break
            if z["type"] == "supply" and not bullish and z_lo <= h <= z_hi:
                hit_zone = z; side = "sell"; break
        if hit_zone is None:
            continue

        r2, r4, r8 = _fwd_returns(closes, i, c)
        body_pct = (c - l) / rng if bullish else (h - c) / rng

        signals.append({
            "dt": dts[i], "side": side,
            "category": "zone",
            "label": "Demand zone" if side == "buy" else "Supply zone",
            "key_level": f"{hit_zone['low']:,.0f}–{hit_zone['high']:,.0f} ({hit_zone['touches']}× touched)",
            "open": o, "high": h, "low": l, "close": c,
            "body_ratio": round(body_pct, 2),
            "ret_2h": r2, "ret_4h": r4, "ret_8h": r8,
        })

    return signals


def detect_pdh_pdl_signals(df: pd.DataFrame,
                            tolerance_pct: float = 0.004,
                            body_ratio: float = 0.35) -> list[dict]:
    """
    Prior Day High / Low rejection.
    PDH reject (SELL): 1H high within ± tol of yesterday's high + bearish body.
    PDL bounce (BUY):  1H low  within ± tol of yesterday's low  + bullish body.
    """
    d = df.copy()
    d["date"] = d["_dt"].dt.date
    daily = d.groupby("date").agg(dh=("high", "max"), dl=("low", "min")).reset_index()
    daily["pdh"] = daily["dh"].shift(1)
    daily["pdl"] = daily["dl"].shift(1)
    d = d.merge(daily[["date", "pdh", "pdl"]], on="date", how="left")

    opens  = d["open"].values
    highs  = d["high"].values
    lows   = d["low"].values
    closes = d["close"].values
    dts    = d["dt"].values
    pdhs   = d["pdh"].values
    pdls   = d["pdl"].values

    signals = []
    for i in range(len(d)):
        pdh, pdl = pdhs[i], pdls[i]
        if pd.isna(pdh) or pd.isna(pdl):
            continue
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        rng = h - l
        if rng == 0 or abs(c - o) / rng < body_ratio:
            continue

        r2, r4, r8 = _fwd_returns(closes, i, c)

        # PDH rejection
        if c < o and abs(h - pdh) <= pdh * tolerance_pct:
            signals.append({
                "dt": dts[i], "side": "sell",
                "category": "pdh_pdl", "label": "PDH reject",
                "key_level": f"PDH {pdh:,.0f}",
                "open": o, "high": h, "low": l, "close": c,
                "body_ratio": round((h - c) / rng, 2),
                "ret_2h": r2, "ret_4h": r4, "ret_8h": r8,
            })
        # PDL bounce
        elif c > o and abs(l - pdl) <= pdl * tolerance_pct:
            signals.append({
                "dt": dts[i], "side": "buy",
                "category": "pdh_pdl", "label": "PDL bounce",
                "key_level": f"PDL {pdl:,.0f}",
                "open": o, "high": h, "low": l, "close": c,
                "body_ratio": round((c - l) / rng, 2),
                "ret_2h": r2, "ret_4h": r4, "ret_8h": r8,
            })

    return signals


def detect_gap_fade_signals(df: pd.DataFrame,
                             gap_pct: float = 0.004,
                             body_ratio: float = 0.40,
                             max_candles: int = 3) -> list[dict]:
    """
    Gap and fade — catches gap-up rejections and gap-down reclaims.

    Gap-up fade (SELL):  Day opens ≥ +gap_pct above prior close, then within first
                         `max_candles` a 1H candle closes BELOW day_open with bearish body.
    Gap-down reclaim (BUY): Day opens ≤ -gap_pct below prior close, then within first
                         `max_candles` a 1H candle closes ABOVE day_open with bullish body.
    """
    d = df.copy().reset_index(drop=True)
    d["date"] = d["_dt"].dt.date

    first = d.groupby("date")["open"].first().reset_index().rename(columns={"open": "day_open"})
    last  = d.groupby("date")["close"].last().reset_index().rename(columns={"close": "day_close"})
    daily = first.merge(last, on="date")
    daily["prev_close"] = daily["day_close"].shift(1)
    daily["gap"] = (daily["day_open"] - daily["prev_close"]) / daily["prev_close"]

    closes = d["close"].values

    signals = []
    for _, day_row in daily.iterrows():
        gap = day_row["gap"]
        if pd.isna(gap) or abs(gap) < gap_pct:
            continue
        day_open = day_row["day_open"]
        is_gap_up = gap > 0

        day_candles = d[d["date"] == day_row["date"]]
        if len(day_candles) < 2:
            continue

        # Skip the first candle, look for the fade in the next few
        for offset in range(1, min(max_candles + 1, len(day_candles))):
            row = day_candles.iloc[offset]
            i = day_candles.index[offset]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            rng = h - l
            if rng == 0 or abs(c - o) / rng < body_ratio:
                continue

            if is_gap_up and c < day_open and c < o:
                r2, r4, r8 = _fwd_returns(closes, i, c)
                signals.append({
                    "dt": row["dt"], "side": "sell",
                    "category": "gap_fade", "label": "Gap-up fade",
                    "key_level": f"Gap +{gap*100:.2f}%, open {day_open:,.0f}",
                    "open": o, "high": h, "low": l, "close": c,
                    "body_ratio": round((h - c) / rng, 2),
                    "ret_2h": r2, "ret_4h": r4, "ret_8h": r8,
                })
                break
            if (not is_gap_up) and c > day_open and c > o:
                r2, r4, r8 = _fwd_returns(closes, i, c)
                signals.append({
                    "dt": row["dt"], "side": "buy",
                    "category": "gap_fade", "label": "Gap-down reclaim",
                    "key_level": f"Gap {gap*100:.2f}%, open {day_open:,.0f}",
                    "open": o, "high": h, "low": l, "close": c,
                    "body_ratio": round((c - l) / rng, 2),
                    "ret_2h": r2, "ret_4h": r4, "ret_8h": r8,
                })
                break

    return signals


# ── Backtest engine ──────────────────────────────────────────────────────────

def backtest_signal(df: pd.DataFrame, signal: dict,
                     max_sl_pts: float = 120, rr_ratio: float = 2.0,
                     wick_buffer: float = 10,
                     be_trigger_pct: float = 0.8, trail_buffer: float = 5) -> dict | None:
    """
    Backtest a single signal forward through df.

    Rules:
      • Entry: next candle's OPEN after the signal candle
      • Initial SL: just beyond signal candle's OPPOSITE wick + wick_buffer,
                    capped at max_sl_pts from entry
      • Target: rr_ratio × SL distance (1:2 R:R → 240pt target for 120pt SL)
      • At be_trigger_pct × target: SL → entry (breakeven)
      • At target: switch to TRAIL mode, SL starts at entry
      • In TRAIL: SL = last 3-bar swing low (buy) / swing high (sell) ± trail_buffer

    Returns trade dict or None if entry/setup impossible.
    """
    sig_dt = pd.to_datetime(signal["dt"])
    matches = df.index[df["_dt"] == sig_dt]
    if len(matches) == 0:
        return None
    entry_idx = matches[0] + 1
    if entry_idx >= len(df):
        return None

    side = signal["side"]
    sign = 1 if side == "buy" else -1
    entry_price = float(df["open"].iloc[entry_idx])
    entry_dt    = df["_dt"].iloc[entry_idx]

    # Dynamic SL: signal candle's opposite wick + buffer, capped at max_sl_pts
    if side == "buy":
        wick_sl_distance = (entry_price - signal["low"]) + wick_buffer
    else:
        wick_sl_distance = (signal["high"] - entry_price) + wick_buffer
    sl_pts = max(5.0, min(wick_sl_distance, max_sl_pts))  # floor at 5 to avoid zero-risk trades
    target_pts = sl_pts * rr_ratio

    sl         = entry_price - sl_pts * sign
    target     = entry_price + target_pts * sign
    be_trigger = entry_price + target_pts * be_trigger_pct * sign

    be_moved  = False
    in_trail  = False
    trail_sl  = None

    for j in range(entry_idx, len(df)):
        h = float(df["high"].iloc[j])
        l = float(df["low"].iloc[j])

        active_sl = trail_sl if in_trail else sl
        sl_hit = (l <= active_sl) if side == "buy" else (h >= active_sl)
        if sl_hit:
            status = "trail" if in_trail else ("be" if be_moved else "sl")
            return _trade_dict(signal, entry_dt, df["_dt"].iloc[j],
                               entry_price, active_sl, sign, sl_pts, status, j - entry_idx + 1)

        # Target hit → start TRAIL mode (initial trail SL = entry / BE)
        target_hit = (h >= target) if side == "buy" else (l <= target)
        if not in_trail and target_hit:
            in_trail = True
            trail_sl = entry_price

        # 80% threshold → move SL to entry
        if not in_trail and not be_moved:
            be_hit = (h >= be_trigger) if side == "buy" else (l <= be_trigger)
            if be_hit:
                sl = entry_price
                be_moved = True

        # Trail update: candle j-1 confirmed as swing pivot if it's lower (for buy) than both neighbours
        if in_trail and j >= entry_idx + 2:
            if side == "buy":
                p_low  = float(df["low"].iloc[j - 1])
                pp_low = float(df["low"].iloc[j - 2])
                if p_low < pp_low and p_low < l:
                    new_sl = p_low - trail_buffer
                    if new_sl > trail_sl:
                        trail_sl = new_sl
            else:
                p_high  = float(df["high"].iloc[j - 1])
                pp_high = float(df["high"].iloc[j - 2])
                if p_high > pp_high and p_high > h:
                    new_sl = p_high + trail_buffer
                    if new_sl < trail_sl:
                        trail_sl = new_sl

    # End of data — trade still open
    last_close = float(df["close"].iloc[-1])
    return _trade_dict(signal, entry_dt, df["_dt"].iloc[-1],
                       entry_price, last_close, sign, sl_pts, "open", len(df) - entry_idx)


def _trade_dict(signal, entry_dt, exit_dt, entry, exit_, sign, sl_pts, status, candles_held):
    pnl = (exit_ - entry) * sign
    return {
        "signal_dt":    pd.Timestamp(signal["dt"]),
        "entry_dt":     pd.Timestamp(entry_dt),
        "exit_dt":      pd.Timestamp(exit_dt),
        "entry":        entry,
        "exit":         exit_,
        "sl_pts":       round(sl_pts, 1),
        "pnl_pts":      round(pnl, 2),
        "r_mult":       round(pnl / sl_pts, 2) if sl_pts else 0,
        "status":       status,
        "candles_held": candles_held,
        "side":         signal["side"],
        "label":        signal["label"],
        "category":     signal["category"],
    }


# ── Composite market mood score ───────────────────────────────────────────────

def compute_mood(df_vix, df_ad, df_fiidii, df_indices, df_nifty):
    score = 0
    factors = []

    # 1. VIX
    if df_vix is not None:
        vcol = next((c for c in df_vix.columns if "close" in c.lower() or "vix" in c.lower()), df_vix.columns[-1])
        df_vix[vcol] = pd.to_numeric(df_vix[vcol], errors="coerce")
        vix = df_vix[vcol].dropna().iloc[-1]
        if vix < 14:   s, lbl = +2, f"VIX {vix:.1f} 🟢"
        elif vix < 18: s, lbl = +1, f"VIX {vix:.1f} 🟡"
        elif vix < 22: s, lbl = 0,  f"VIX {vix:.1f} ⚠️"
        elif vix < 27: s, lbl = -1, f"VIX {vix:.1f} 🔴"
        else:          s, lbl = -2, f"VIX {vix:.1f} 💀"
        score += s; factors.append(lbl)

    # 2. FII net
    if df_fiidii is not None and "netValue" in df_fiidii.columns:
        df_fiidii["netValue"] = pd.to_numeric(df_fiidii["netValue"], errors="coerce")
        fii_row = df_fiidii[df_fiidii["category"].str.contains("FII|FPI", na=False, case=False)]
        if not fii_row.empty:
            net = fii_row["netValue"].iloc[-1]
            if net > 1000:   s, lbl = +2, f"FII +₹{net:,.0f}Cr 🟢"
            elif net > 0:    s, lbl = +1, f"FII +₹{net:,.0f}Cr 🟡"
            elif net > -1000: s, lbl = -1, f"FII ₹{net:,.0f}Cr 🔴"
            else:            s, lbl = -2, f"FII ₹{net:,.0f}Cr 💀"
            score += s; factors.append(lbl)

    # 3. Advance/Decline
    if df_ad is not None and not df_ad.empty:
        latest = df_ad.iloc[-1]
        try:
            ratio = float(latest["advances"]) / max(float(latest["declines"]), 1)
            if ratio > 2.5:  s, lbl = +2, f"A/D {ratio:.1f} 🟢"
            elif ratio > 1.5: s, lbl = +1, f"A/D {ratio:.1f} 🟡"
            elif ratio > 0.7: s, lbl = 0,  f"A/D {ratio:.1f} ⚪"
            elif ratio > 0.4: s, lbl = -1, f"A/D {ratio:.1f} 🔴"
            else:             s, lbl = -2, f"A/D {ratio:.1f} 💀"
            score += s; factors.append(lbl)
        except Exception:
            pass

    # 4. Nifty daily % change
    if df_nifty is not None and "CLOSE_INDEX_VAL" in df_nifty.columns:
        df_nifty["CLOSE_INDEX_VAL"] = pd.to_numeric(df_nifty["CLOSE_INDEX_VAL"], errors="coerce")
        closes = df_nifty["CLOSE_INDEX_VAL"].dropna()
        if len(closes) >= 2:
            pct = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
            if pct > 1:    s, lbl = +2, f"Nifty {pct:+.2f}% 🟢"
            elif pct > 0:  s, lbl = +1, f"Nifty {pct:+.2f}% 🟡"
            elif pct > -1: s, lbl = -1, f"Nifty {pct:+.2f}% 🔴"
            else:          s, lbl = -2, f"Nifty {pct:+.2f}% 💀"
            score += s; factors.append(lbl)

    # 5. Sector breadth
    if df_indices is not None and "percentChange" in df_indices.columns:
        df_indices["percentChange"] = pd.to_numeric(df_indices["percentChange"], errors="coerce")
        pcts = df_indices["percentChange"].dropna()
        if len(pcts) > 5:
            bull_frac = (pcts > 0).sum() / len(pcts)
            if bull_frac > 0.75:  s, lbl = +1, f"Sectors {bull_frac*100:.0f}% green 🟢"
            elif bull_frac < 0.35: s, lbl = -1, f"Sectors {bull_frac*100:.0f}% green 🔴"
            else:                  s, lbl = 0,  f"Sectors {bull_frac*100:.0f}% green ⚪"
            score += s; factors.append(lbl)

    # Map score → mood
    if score >= 6:    mood, color, advice = "SUPER BULLISH", GREEN, "Strong institutional buying across sectors. Ride the trend — high conviction longs, minimal hedging."
    elif score >= 3:  mood, color, advice = "BULLISH", GREEN,  "Market leaning up. Favour longs on pullbacks. Keep stops tight."
    elif score >= 1:  mood, color, advice = "MILDLY BULLISH", "#7ec8a0", "Slight edge to bulls but breadth is mixed. Be selective — only high-conviction trades."
    elif score >= -1: mood, color, advice = "NEUTRAL", YELLOW, "No clear edge. Wait for a setup. Preserve capital — reduce size."
    elif score >= -3: mood, color, advice = "MILDLY BEARISH", "#f0a070", "Bears have a slight edge. Reduce longs, hedge open positions."
    elif score >= -5: mood, color, advice = "BEARISH", RED,   "Institutional selling visible. Avoid fresh longs. Tight stops or cash."
    else:             mood, color, advice = "SUPER BEARISH", RED, "Panic/distribution visible. Stay out or hedge everything. Capital preservation first."

    return score, mood, color, advice, factors


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════════════════════════════

df_vix       = load("vix")
df_ad        = load("advance_decline")
df_fiidii    = load("fii_dii")
df_indices   = load("all_indices")
df_nifty     = load("nifty_ohlc")
df_nifty_1h  = load("nifty_1h")
df_sh      = load("sector_history")
df_poi     = load("participant_oi")
df_fiider  = load("fii_derivatives")
df_bulk    = load("bulk_deals")
df_block   = load("block_deals")
df_hd      = load("high_delivery")
df_52      = load("week_52_high_low")
df_mav     = load("most_active_value")
df_mavol   = load("most_active_volume")
df_g       = load("top_gainers")
df_l       = load("top_losers")
meta       = load_meta()

score, mood, mood_color, advice, factors = compute_mood(
    df_vix, df_ad, df_fiidii, df_indices, df_nifty
)


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

def fmt_ts(ts):
    if not ts or ts == "Never":
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%d %b, %I:%M %p")
    except Exception:
        return ts

h1, h2 = st.columns([5, 2])
with h1:
    st.markdown(f'<span style="font-size:1.4rem;font-weight:700;color:{WHITE}">📈 NSE Dashboard</span>', unsafe_allow_html=True)
with h2:
    last = meta.get("last_eod_fetch") or meta.get("last_quick_fetch") or "Never"
    st.markdown(f'<span style="font-size:0.72rem;color:{MUTED}">Last updated: {fmt_ts(last)}</span>', unsafe_allow_html=True)
    if st.button("⟳ Refresh", type="secondary"):
        with st.spinner("Fetching from NSE…"):
            r = subprocess.run(
                [sys.executable, str(Path(__file__).parent / "fetcher.py"), "quick"],
                capture_output=True, text=True, timeout=360
            )
        if r.returncode == 0:
            st.rerun()
        else:
            st.error(r.stderr[-1500:])


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET MOOD BANNER
# ═══════════════════════════════════════════════════════════════════════════════

factor_pills = "".join(
    f'<span class="factor-pill">{f}</span>' for f in factors
)
st.markdown(f"""
<div class="mood-banner" style="background: linear-gradient(135deg, {mood_color}18, {SURFACE} 60%);">
  <div>
    <div class="mood-score" style="color:{mood_color}">{score:+d}</div>
    <div style="font-size:0.65rem;color:{MUTED};margin-top:2px">MOOD SCORE / 9</div>
  </div>
  <div>
    <div class="mood-label" style="color:{mood_color}">{mood}</div>
    <div class="mood-advice">{advice}</div>
  </div>
  <div class="mood-factors">{factor_pills}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# NIFTY CHART + ZONES
# ═══════════════════════════════════════════════════════════════════════════════

sec("NIFTY 50 — PRICE ACTION & KEY ZONES", "📊")

if df_nifty is not None and "CLOSE_INDEX_VAL" in df_nifty.columns:
    df_n = df_nifty.copy()
    for c in ["OPEN_INDEX_VAL", "HIGH_INDEX_VAL", "LOW_INDEX_VAL", "CLOSE_INDEX_VAL", "TURN_OVER"]:
        if c in df_n.columns:
            df_n[c] = pd.to_numeric(df_n[c], errors="coerce")
    df_n = df_n.dropna(subset=["OPEN_INDEX_VAL", "HIGH_INDEX_VAL", "LOW_INDEX_VAL", "CLOSE_INDEX_VAL"])

    # ── Fix: parse dates properly so chronological order is correct ──────────
    df_n["_dt"] = pd.to_datetime(df_n["TIMESTAMP"], format="%d-%b-%Y", errors="coerce")
    df_n = df_n.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)

    current_price = df_n["CLOSE_INDEX_VAL"].iloc[-1]
    prev_price    = df_n["CLOSE_INDEX_VAL"].iloc[-2]
    day_chg       = current_price - prev_price
    day_pct       = day_chg / prev_price * 100
    chg_color     = GREEN if day_chg >= 0 else RED

    # Key stat row (4 cards, no EMAs)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(stat_card("NIFTY 50", f"{current_price:,.2f}",
        f'<span style="color:{chg_color}">{day_chg:+,.2f} ({day_pct:+.2f}%)</span>', WHITE),
        unsafe_allow_html=True)
    c2.markdown(stat_card("Day High",  f"{df_n['HIGH_INDEX_VAL'].iloc[-1]:,.2f}"), unsafe_allow_html=True)
    c3.markdown(stat_card("Day Low",   f"{df_n['LOW_INDEX_VAL'].iloc[-1]:,.2f}"), unsafe_allow_html=True)
    c4.markdown(stat_card("6M Range",  f"{df_n['LOW_INDEX_VAL'].min():,.0f} – {df_n['HIGH_INDEX_VAL'].max():,.0f}"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Detect zones (using datetime index now)
    zones = detect_zones(df_n)
    demand_zones = sorted([z for z in zones if z["type"] == "demand"], key=lambda z: abs((z["low"]+z["high"])/2 - current_price))
    supply_zones = sorted([z for z in zones if z["type"] == "supply"], key=lambda z: abs((z["low"]+z["high"])/2 - current_price))

    # 1H signals — compute zones from the 1H chart itself for more precise marking
    zone_signals = []
    df_1h_clean = None
    zones_1h = []
    if df_nifty_1h is not None and not df_nifty_1h.empty:
        df_1h_clean = df_nifty_1h.copy()
        for col in ["open", "high", "low", "close"]:
            df_1h_clean[col] = pd.to_numeric(df_1h_clean[col], errors="coerce")
        df_1h_clean["_dt"] = pd.to_datetime(df_1h_clean["dt"], errors="coerce")
        df_1h_clean = df_1h_clean.dropna(subset=["_dt", "open", "close"]).sort_values("_dt").reset_index(drop=True)

        zones_1h = detect_zones(
            df_1h_clean, tolerance_pct=0.5, window=6,
            cols={"open": "open", "high": "high", "low": "low",
                  "close": "close", "date": "dt"},
        )
        zone_signals = (
            detect_zone_touch_signals(df_1h_clean, zones_1h)
            + detect_pdh_pdl_signals(df_1h_clean)
            + detect_gap_fade_signals(df_1h_clean)
        )
        zone_signals.sort(key=lambda s: pd.Timestamp(s["dt"]))

    has_volume = "TURN_OVER" in df_n.columns and df_n["TURN_OVER"].notna().sum() > 5

    tab_daily, tab_1h = st.tabs(["📅 Daily — Zones & Context", "⏱ 1H — Entry Signals"])

    with tab_daily:
        # ── Build chart ───────────────────────────────────────────────────────
        row_heights = [0.78, 0.22] if has_volume else [1.0]
        rows = 2 if has_volume else 1
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.015,
            row_heights=row_heights,
        )

        for z in zones:
            is_demand = z["type"] == "demand"
            alpha = min(0.08 + 0.04 * z["touches"], 0.22)
            fc = f"rgba(34,171,148,{alpha})" if is_demand else f"rgba(235,87,87,{alpha})"
            lc = "rgba(34,171,148,0.6)"      if is_demand else "rgba(235,87,87,0.6)"
            fig.add_hrect(y0=z["low"], y1=z["high"], fillcolor=fc,
                          line=dict(color=lc, width=0.8), layer="below", row=1, col=1)
            tag = f"{'D' if is_demand else 'S'}{z['touches']}  {z['low']:,.0f}"
            fig.add_annotation(x=df_n["_dt"].iloc[-1], y=z["low"], text=tag,
                               showarrow=False, xanchor="left", yanchor="bottom",
                               font=dict(size=8.5, color=lc), bgcolor="rgba(15,15,15,0)", borderpad=2)
            for rev in z.get("reversals", []):
                rev_dt = pd.to_datetime(rev["date"], format="%d-%b-%Y", errors="coerce")
                if pd.isna(rev_dt): continue
                fig.add_trace(go.Scatter(
                    x=[rev_dt], y=[rev["price"]], mode="markers",
                    marker=dict(symbol="triangle-up" if is_demand else "triangle-down",
                                size=10, color=lc, line=dict(color=WHITE, width=0.8)),
                    showlegend=False,
                    hovertemplate=f"<b>{'Bounce ▲' if is_demand else 'Rejection ▼'}</b><br>%{{x|%d %b %Y}}<br>%{{y:,.0f}}<extra></extra>",
                ), row=1, col=1)

        fig.add_trace(go.Candlestick(
            x=df_n["_dt"],
            open=df_n["OPEN_INDEX_VAL"], high=df_n["HIGH_INDEX_VAL"],
            low=df_n["LOW_INDEX_VAL"],   close=df_n["CLOSE_INDEX_VAL"],
            increasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),
            decreasing=dict(line=dict(color=RED,   width=1), fillcolor=RED),
            name="NIFTY 50", showlegend=False,
            hovertext=[f"O {o:,.2f}  H {h:,.2f}  L {l:,.2f}  C {c:,.2f}"
                       for o, h, l, c in zip(df_n["OPEN_INDEX_VAL"], df_n["HIGH_INDEX_VAL"],
                                              df_n["LOW_INDEX_VAL"], df_n["CLOSE_INDEX_VAL"])],
            hoverinfo="text+x",
        ), row=1, col=1)

        fig.add_hline(y=current_price, line_dash="dash",
                      line_color="rgba(255,255,255,0.35)", line_width=1,
                      annotation_text=f" {current_price:,.2f}", annotation_position="right",
                      annotation=dict(font=dict(size=10, color=WHITE), bgcolor="rgba(0,0,0,0.6)"),
                      row=1, col=1)

        if has_volume:
            vol_colors = ["rgba(34,171,148,0.5)" if c >= o else "rgba(235,87,87,0.5)"
                          for c, o in zip(df_n["CLOSE_INDEX_VAL"], df_n["OPEN_INDEX_VAL"])]
            fig.add_trace(go.Bar(x=df_n["_dt"], y=df_n["TURN_OVER"],
                                 marker_color=vol_colors, showlegend=False,
                                 hovertemplate="%{x|%d %b}<br>Vol: %{y:,.0f} Cr<extra></extra>"),
                          row=2, col=1)

        fig.update_layout(
            paper_bgcolor=BG, plot_bgcolor=BG,
            font=dict(color=TEXT, family="Inter, sans-serif", size=11),
            height=580, margin=dict(l=8, r=80, t=16, b=8),
            showlegend=False, hovermode="x unified",
            xaxis=dict(rangeslider_visible=False,
                       gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.04)",
                       tickformat="%b '%y", tickfont=dict(size=10),
                       showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="dot",
                       type="date"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.04)",
                       tickfont=dict(size=10), tickformat=",.0f",
                       showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="dot",
                       side="right"),
        )
        if has_volume:
            fig.update_layout(
                xaxis2=dict(gridcolor="rgba(255,255,255,0.04)",
                            tickformat="%b '%y", tickfont=dict(size=9), type="date"),
                yaxis2=dict(gridcolor="rgba(255,255,255,0.04)",
                            tickfont=dict(size=9), tickformat=".0s",
                            title=dict(text="Vol", font=dict(size=9)), side="right"),
            )

        st.plotly_chart(fig, use_container_width=True)

        # ── Zone table ────────────────────────────────────────────────────────
        if zones:
            zone_rows = []
            for z in sorted(zones, key=lambda x: x["low"], reverse=True):
                mid  = (z["low"] + z["high"]) / 2
                dist = (current_price - mid) / current_price * 100
                zone_rows.append({
                    "Type":          "🟢 Demand" if z["type"] == "demand" else "🔴 Supply",
                    "Zone":          f"{z['low']:,.0f} – {z['high']:,.0f}",
                    "Width (pts)":   f"{z['high']-z['low']:,.0f}",
                    "Touches":       z["touches"],
                    "Reversals":     len(z.get("reversals", [])),
                    "Dist from CMP": f"{'▼' if dist > 0 else '▲'} {abs(dist):.1f}%",
                })
            st.dataframe(pd.DataFrame(zone_rows), use_container_width=True, hide_index=True)

        # ── Zone interpretation ───────────────────────────────────────────────
        if demand_zones:
            dz   = demand_zones[0]
            dist = (current_price - dz["high"]) / current_price * 100
            revs = len(dz.get("reversals", []))
            if abs(dist) < 1.0:
                interp(f"Price is **inside the demand zone {dz['low']:,.0f}–{dz['high']:,.0f}** right now "
                       f"({dz['touches']} touches, {revs} confirmed bounces). "
                       f"High-probability reversal area — wait for a bullish 1H candle to confirm. Stop below {dz['low']:,.0f}.")
            elif dist > 0:
                interp(f"Nearest demand zone: **{dz['low']:,.0f}–{dz['high']:,.0f}** ({dist:.1f}% below, "
                       f"{dz['touches']} touches, {revs} bounces). If price pulls back here, watch for reversal on the 1H chart.")
        if supply_zones:
            sz   = supply_zones[0]
            dist = (sz["low"] - current_price) / current_price * 100
            revs = len(sz.get("reversals", []))
            if abs(dist) < 1.0:
                interp(f"Price is **approaching supply zone {sz['low']:,.0f}–{sz['high']:,.0f}** "
                       f"({sz['touches']} touches, {revs} rejections). Tighten stops or trim longs. "
                       f"Wait for a bearish 1H candle to confirm rejection before shorting.")
            elif dist > 0:
                interp(f"Nearest supply zone: **{sz['low']:,.0f}–{sz['high']:,.0f}** ({dist:.1f}% above, {sz['touches']} touches). Room to run before resistance.")

    with tab_1h:
        if df_1h_clean is not None and not df_1h_clean.empty:
            # Default to last ~15 trading days (105 candles) — keeps signals visible without zooming
            recent_n = min(len(df_1h_clean), 105)
            df_view = df_1h_clean.tail(recent_n).reset_index(drop=True)
            view_start = df_view["_dt"].iloc[0]
            view_end   = df_view["_dt"].iloc[-1]

            # Y-axis bounds with breathing room
            y_lo = df_view["low"].min()
            y_hi = df_view["high"].max()
            pad  = (y_hi - y_lo) * 0.04

            fig1h = go.Figure()

            # Zone bands (computed from 1H wicks/closes)
            for z in zones_1h:
                is_demand = z["type"] == "demand"
                alpha = min(0.07 + 0.035 * z["touches"], 0.20)
                fc = f"rgba(34,171,148,{alpha})" if is_demand else f"rgba(235,87,87,{alpha})"
                lc = "rgba(34,171,148,0.55)"     if is_demand else "rgba(235,87,87,0.55)"
                fig1h.add_hrect(y0=z["low"], y1=z["high"], fillcolor=fc,
                                line=dict(color=lc, width=0.6), layer="below")
                fig1h.add_annotation(
                    x=view_end, y=(z["low"] + z["high"]) / 2,
                    text=f"{'D' if is_demand else 'S'}{z['touches']}  {z['low']:,.0f}",
                    showarrow=False, xanchor="left", yanchor="middle",
                    font=dict(size=8.5, color=lc), bgcolor="rgba(15,15,15,0)", borderpad=2,
                )

            fig1h.add_trace(go.Candlestick(
                x=df_1h_clean["_dt"],
                open=df_1h_clean["open"], high=df_1h_clean["high"],
                low=df_1h_clean["low"],   close=df_1h_clean["close"],
                increasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),
                decreasing=dict(line=dict(color=RED,   width=1), fillcolor=RED),
                name="NIFTY 1H", showlegend=False,
                hovertext=[f"O {o:,.0f}  H {h:,.0f}  L {l:,.0f}  C {c:,.0f}"
                           for o, h, l, c in zip(df_1h_clean["open"], df_1h_clean["high"],
                                                  df_1h_clean["low"], df_1h_clean["close"])],
                hoverinfo="text+x",
            ))

            # Signal markers — different symbols per category, unified buy=green / sell=red
            # zone     → triangle, pdh_pdl → diamond, gap_fade → star
            cat_symbol = {"zone": "triangle-up", "pdh_pdl": "diamond", "gap_fade": "star"}
            cat_symbol_sell = {"zone": "triangle-down", "pdh_pdl": "diamond", "gap_fade": "star"}

            traces_by_key = {}  # (side, category) → {x, y, hover}
            for sig in zone_signals:
                sig_dt = pd.to_datetime(sig["dt"], errors="coerce")
                if pd.isna(sig_dt): continue
                side = sig["side"]
                cat  = sig["category"]
                r2h  = sig["ret_2h"]
                ret_line = f"+1H: {r2h:+.2f}%<br>" if r2h is not None else ""
                arrow = "▲" if side == "buy" else "▼"
                hover = (
                    f"<b>{arrow} {sig['label']}</b><br>"
                    f"{sig_dt.strftime('%d %b %H:%M')}<br>"
                    f"{sig['key_level']}<br>"
                    f"Body: {sig['body_ratio']:.0%}<br>"
                    f"{ret_line}<extra></extra>"
                )
                # Place markers offset further per category to avoid overlap when multiple fire on same candle
                offset_idx = {"zone": 1, "pdh_pdl": 2, "gap_fade": 3}[cat]
                if side == "buy":
                    y = sig["low"] * (1 - 0.0028 * offset_idx)
                else:
                    y = sig["high"] * (1 + 0.0028 * offset_idx)
                key = (side, cat)
                traces_by_key.setdefault(key, {"x": [], "y": [], "hover": []})
                traces_by_key[key]["x"].append(sig_dt)
                traces_by_key[key]["y"].append(y)
                traces_by_key[key]["hover"].append(hover)

            for (side, cat), data in traces_by_key.items():
                clr = GREEN if side == "buy" else RED
                sym = cat_symbol[cat] if side == "buy" else cat_symbol_sell[cat]
                size = 8 if cat == "zone" else (9 if cat == "pdh_pdl" else 11)
                fig1h.add_trace(go.Scatter(
                    x=data["x"], y=data["y"], mode="markers",
                    marker=dict(symbol=sym, size=size, color=clr,
                                line=dict(color="rgba(0,0,0,0.5)", width=0.5)),
                    showlegend=False, hovertext=data["hover"], hoverinfo="text",
                ))

            fig1h.add_hline(y=current_price, line_dash="dash",
                            line_color="rgba(255,255,255,0.35)", line_width=1,
                            annotation_text=f" {current_price:,.0f}",
                            annotation_position="right",
                            annotation=dict(font=dict(size=10, color=WHITE), bgcolor="rgba(0,0,0,0.6)"))

            fig1h.update_layout(
                paper_bgcolor=BG, plot_bgcolor=BG,
                font=dict(color=TEXT, family="Inter, sans-serif", size=11),
                height=620, margin=dict(l=8, r=85, t=50, b=8),
                showlegend=False, hovermode="x unified", dragmode="pan",
                xaxis=dict(
                    rangeslider_visible=False,
                    gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.04)",
                    tickformat="%d %b\n%H:%M", tickfont=dict(size=9),
                    showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="dot",
                    type="date",
                    range=[view_start, view_end],
                    rangebreaks=[
                        dict(bounds=["sat", "mon"]),
                        dict(bounds=[15.5, 9.25], pattern="hour"),
                    ],
                    rangeselector=dict(
                        buttons=[
                            dict(count=1,  label="1D",  step="day",   stepmode="backward"),
                            dict(count=3,  label="3D",  step="day",   stepmode="backward"),
                            dict(count=7,  label="1W",  step="day",   stepmode="backward"),
                            dict(count=15, label="2W",  step="day",   stepmode="backward"),
                            dict(count=1,  label="1M",  step="month", stepmode="backward"),
                            dict(step="all", label="All"),
                        ],
                        bgcolor="rgba(26,26,46,0.8)",
                        activecolor=BLUE,
                        font=dict(color=TEXT, size=10),
                        x=0, y=1.08, xanchor="left", yanchor="bottom",
                    ),
                ),
                yaxis=dict(
                    gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.04)",
                    tickfont=dict(size=10), tickformat=",.0f",
                    showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="dot",
                    side="right",
                    autorange=False,
                    range=[y_lo - pad, y_hi + pad],
                ),
            )

            # Render via raw HTML so we can inject JS that auto-rescales Y when X changes
            chart_html = pio.to_html(
                fig1h, include_plotlyjs="cdn", full_html=False,
                config={"scrollZoom": True, "displaylogo": False, "responsive": True,
                        "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
                div_id="nifty1h-chart",
            )
            auto_rescale_js = """
<script>
(function() {
  function hookChart() {
    var gd = document.getElementById('nifty1h-chart');
    if (!gd || !gd.on) { setTimeout(hookChart, 80); return; }
    var busy = false;
    gd.on('plotly_relayout', function(ev) {
      if (busy) return;
      if (!('xaxis.range[0]' in ev || 'xaxis.range[1]' in ev ||
            'xaxis.autorange' in ev || 'xaxis.range' in ev)) return;

      var xr = gd.layout.xaxis.range;
      if (!xr || xr.length !== 2) return;
      var xs = new Date(xr[0]).getTime();
      var xe = new Date(xr[1]).getTime();

      var ymin = Infinity, ymax = -Infinity;
      gd.data.forEach(function(tr) {
        if (!tr.x) return;
        for (var i = 0; i < tr.x.length; i++) {
          var t = new Date(tr.x[i]).getTime();
          if (t < xs || t > xe) continue;
          // candlestick: use high/low
          if (tr.type === 'candlestick') {
            if (tr.high[i] > ymax) ymax = tr.high[i];
            if (tr.low[i]  < ymin) ymin = tr.low[i];
          } else if (tr.y && tr.y[i] != null) {
            if (tr.y[i] > ymax) ymax = tr.y[i];
            if (tr.y[i] < ymin) ymin = tr.y[i];
          }
        }
      });

      if (!isFinite(ymin) || !isFinite(ymax)) return;
      var pad = (ymax - ymin) * 0.04 || 10;
      busy = true;
      Plotly.relayout(gd, {'yaxis.range': [ymin - pad, ymax + pad]})
        .then(function(){ busy = false; });
    });
  }
  hookChart();
})();
</script>
"""
            components.html(chart_html + auto_rescale_js, height=680, scrolling=False)

            st.caption("**Auto-rescales Y on zoom/pan.** Click 1D / 3D / 1W / 2W / 1M / All to switch views. "
                       "Scroll on chart to zoom, drag to pan.")

            # ── Zone summary table (1H zones) ────────────────────────────────
            if zones_1h:
                zrows = []
                for z in sorted(zones_1h, key=lambda x: x["low"], reverse=True):
                    mid = (z["low"] + z["high"]) / 2
                    dist = (current_price - mid) / current_price * 100
                    zrows.append({
                        "Type":         "🟢 Demand" if z["type"] == "demand" else "🔴 Supply",
                        "Zone":         f"{z['low']:,.0f} – {z['high']:,.0f}",
                        "Width (pts)":  f"{z['high']-z['low']:,.0f}",
                        "Touches":      z["touches"],
                        "Dist from CMP": f"{'▼' if dist > 0 else '▲'} {abs(dist):.1f}%",
                    })
                st.dataframe(pd.DataFrame(zrows), use_container_width=True, hide_index=True)

            # ── Signal history table ─────────────────────────────────────────
            if zone_signals:
                st.markdown("#### 1H Intraday Signals — Zone-Touch · PDH/PDL · Gap-Fade")

                # Win-rate summary
                outcomes_1 = [s["ret_2h"] for s in zone_signals if s["ret_2h"] is not None]
                outcomes_2 = [s["ret_4h"] for s in zone_signals if s["ret_4h"] is not None]
                if outcomes_1:
                    # Signed return: buy = ret as-is, sell = inverted (a sell that drops is a win)
                    signed_1 = [r if s["side"]=="buy" else -r
                                for s,r in zip(zone_signals, [s["ret_2h"] for s in zone_signals]) if r is not None]
                    signed_2 = [r if s["side"]=="buy" else -r
                                for s,r in zip(zone_signals, [s["ret_4h"] for s in zone_signals]) if r is not None]
                    wins_1 = sum(1 for r in signed_1 if r > 0)
                    avg_1  = round(sum(signed_1) / len(signed_1), 2) if signed_1 else 0
                    avg_2  = round(sum(signed_2) / len(signed_2), 2) if signed_2 else None
                    wc1 = GREEN if wins_1 / len(signed_1) >= 0.55 else (YELLOW if wins_1 / len(signed_1) >= 0.45 else RED)

                    # Per-category counts
                    n_zone = sum(1 for s in zone_signals if s["category"] == "zone")
                    n_pdh  = sum(1 for s in zone_signals if s["category"] == "pdh_pdl")
                    n_gap  = sum(1 for s in zone_signals if s["category"] == "gap_fade")

                    cw = st.columns(4)
                    cw[0].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Total / Zone · PDH · Gap</div>
                        <div class="stat-value" style="font-size:1.4rem">{len(zone_signals)}
                          <span style="font-size:0.7rem;color:{MUTED};font-weight:400">  /  {n_zone}·{n_pdh}·{n_gap}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    cw[1].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">+1H Win Rate (signed)</div>
                        <div class="stat-value" style="font-size:1.6rem;color:{wc1}">{wins_1}/{len(signed_1)}</div>
                    </div>""", unsafe_allow_html=True)
                    cw[2].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Avg +1H (signed)</div>
                        <div class="stat-value" style="font-size:1.6rem;color:{GREEN if avg_1 > 0 else RED}">{avg_1:+.2f}%</div>
                    </div>""", unsafe_allow_html=True)
                    if avg_2 is not None:
                        wins_2 = sum(1 for r in signed_2 if r > 0)
                        wc2 = GREEN if wins_2 / len(signed_2) >= 0.55 else (YELLOW if wins_2 / len(signed_2) >= 0.45 else RED)
                        cw[3].markdown(f"""<div class="stat-card" style="text-align:center">
                            <div class="stat-label">Avg +2H (signed)</div>
                            <div class="stat-value" style="font-size:1.6rem;color:{wc2}">{avg_2:+.2f}%</div>
                        </div>""", unsafe_allow_html=True)

                # Filter by category
                cat_choice = st.radio(
                    "Filter signals:",
                    ["All", "Zone-Touch", "PDH/PDL", "Gap-Fade"],
                    horizontal=True, index=0, label_visibility="collapsed",
                )
                cat_map = {"Zone-Touch": "zone", "PDH/PDL": "pdh_pdl", "Gap-Fade": "gap_fade"}
                view_sigs = zone_signals if cat_choice == "All" else [s for s in zone_signals if s["category"] == cat_map[cat_choice]]

                sig_rows = []
                for s in reversed(view_sigs):
                    sig_dt = pd.to_datetime(s["dt"], errors="coerce")
                    side_emoji = "🟢 Buy" if s["side"] == "buy" else "🔴 Sell"
                    sig_rows.append({
                        "Date/Time":  sig_dt.strftime("%d %b  %H:%M") if not pd.isna(sig_dt) else s["dt"],
                        "Side":       side_emoji,
                        "Signal":     s["label"],
                        "Key Level":  s["key_level"],
                        "Body":       f"{s['body_ratio']:.0%}",
                        "+1H Ret":    s["ret_2h"],
                        "+2H Ret":    s["ret_4h"],
                        "+4H Ret":    s["ret_8h"],
                    })

                if sig_rows:
                    df_sig = pd.DataFrame(sig_rows)

                    def _color_ret(val):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return ""
                        return f"color: {GREEN}" if val > 0 else f"color: {RED}"

                    def _fmt_ret(v):
                        return f"{v:+.2f}%" if v is not None else "—"

                    styled = (
                        df_sig.style
                        .map(_color_ret, subset=["+1H Ret", "+2H Ret", "+4H Ret"])
                        .format({"+1H Ret": _fmt_ret, "+2H Ret": _fmt_ret, "+4H Ret": _fmt_ret})
                    )
                    st.dataframe(styled, use_container_width=True, hide_index=True)

                interp("**Three signal types layered on the 1H chart:**  \n"
                       "▲▼ **Zone-touch** — candle pokes into a 1H demand/supply zone and reverses.  \n"
                       "◆ **PDH / PDL** — candle rejects yesterday's high (sell) or bounces off yesterday's low (buy).  \n"
                       "★ **Gap-fade** — day gaps ≥0.4% and a subsequent 1H candle decisively closes back through day's open.  \n\n"
                       "Win rate is **signed** — a sell signal that drops counts as a win. Confirm with VIX direction and FII futures stance before entering.")

                # ── Backtest ─────────────────────────────────────────────────
                st.markdown("#### 📊 Backtest — Wick-based SL · Configurable")

                # Live-tuning sliders
                sc1, sc2, sc3, sc4 = st.columns(4)
                max_sl_pts = sc1.slider(
                    "Max SL (pts)", min_value=30, max_value=250, value=120, step=5,
                    help="SL is placed just beyond the signal candle's opposite wick + buffer, but capped at this distance from entry.",
                )
                rr_ratio = sc2.slider(
                    "Risk:Reward (Target/SL)", min_value=1.0, max_value=3.0, value=2.0, step=0.1,
                    help="Target distance = R:R × SL distance. 2.0 means a 120-pt SL targets 240 pts.",
                )
                be_trig_pct = sc3.slider(
                    "BE trigger (% of target)", min_value=50, max_value=100, value=80, step=5,
                    help="Move SL to entry once price reaches this fraction of target.",
                ) / 100.0
                wick_buf = sc4.slider(
                    "Wick buffer (pts)", min_value=0, max_value=50, value=10, step=1,
                    help="Extra room beyond the signal candle's wick before the cap kicks in.",
                )

                trades = []
                for s in zone_signals:
                    t = backtest_signal(
                        df_1h_clean, s,
                        max_sl_pts=max_sl_pts, rr_ratio=rr_ratio,
                        wick_buffer=wick_buf, be_trigger_pct=be_trig_pct,
                    )
                    if t is not None:
                        trades.append(t)

                if trades:
                    wins   = [t for t in trades if t["pnl_pts"] > 0]
                    losses = [t for t in trades if t["pnl_pts"] < 0]
                    bes    = [t for t in trades if t["pnl_pts"] == 0]
                    open_  = [t for t in trades if t["status"] == "open"]
                    total_pnl   = sum(t["pnl_pts"] for t in trades)
                    gross_win   = sum(t["pnl_pts"] for t in wins)
                    gross_loss  = sum(t["pnl_pts"] for t in losses)
                    win_rate    = len(wins) / len(trades) * 100
                    not_loss    = (len(wins) + len(bes)) / len(trades) * 100
                    avg_win     = (gross_win / len(wins)) if wins else 0
                    avg_loss    = (gross_loss / len(losses)) if losses else 0
                    profit_factor = abs(gross_win / gross_loss) if losses else float("inf")
                    avg_r       = sum(t["r_mult"] for t in trades) / len(trades)
                    best_trade  = max(trades, key=lambda t: t["pnl_pts"])
                    worst_trade = min(trades, key=lambda t: t["pnl_pts"])

                    # Summary cards
                    bc = st.columns(5)
                    bc[0].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Trades</div>
                        <div class="stat-value" style="font-size:1.4rem">{len(trades)}</div>
                        <div class="stat-sub" style="font-size:0.7rem">
                          <span style="color:{GREEN}">{len(wins)}W</span> · <span style="color:{RED}">{len(losses)}L</span> · {len(bes)}BE · {len(open_)} open
                        </div>
                    </div>""", unsafe_allow_html=True)

                    wr_color = GREEN if win_rate >= 40 else (YELLOW if win_rate >= 25 else RED)
                    bc[1].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Win Rate / Not-Loss</div>
                        <div class="stat-value" style="font-size:1.4rem;color:{wr_color}">{win_rate:.1f}%</div>
                        <div class="stat-sub" style="font-size:0.7rem">Not-loss: {not_loss:.1f}% (incl BE)</div>
                    </div>""", unsafe_allow_html=True)

                    pnl_color = GREEN if total_pnl > 0 else RED
                    bc[2].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Total P&L (pts)</div>
                        <div class="stat-value" style="font-size:1.4rem;color:{pnl_color}">{total_pnl:+,.0f}</div>
                        <div class="stat-sub" style="font-size:0.7rem">Avg/trade: {total_pnl/len(trades):+.1f}</div>
                    </div>""", unsafe_allow_html=True)

                    pf_color = GREEN if profit_factor > 1.5 else (YELLOW if profit_factor > 1.0 else RED)
                    bc[3].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Profit Factor</div>
                        <div class="stat-value" style="font-size:1.4rem;color:{pf_color}">{profit_factor:.2f}</div>
                        <div class="stat-sub" style="font-size:0.7rem">Avg R: {avg_r:+.2f}</div>
                    </div>""", unsafe_allow_html=True)

                    bc[4].markdown(f"""<div class="stat-card" style="text-align:center">
                        <div class="stat-label">Best / Worst (pts)</div>
                        <div class="stat-value" style="font-size:1.4rem">
                          <span style="color:{GREEN}">+{best_trade['pnl_pts']:.0f}</span>
                          <span style="color:{MUTED}"> / </span>
                          <span style="color:{RED}">{worst_trade['pnl_pts']:.0f}</span>
                        </div>
                        <div class="stat-sub" style="font-size:0.7rem">Win: {avg_win:+.0f} · Loss: {avg_loss:+.0f} avg</div>
                    </div>""", unsafe_allow_html=True)

                    # Per-category breakdown
                    st.markdown("###### Performance by signal type")
                    cat_rows = []
                    cat_names = {"zone": "Zone-Touch", "pdh_pdl": "PDH / PDL", "gap_fade": "Gap-Fade"}
                    for cat, name in cat_names.items():
                        ct = [t for t in trades if t["category"] == cat]
                        if not ct: continue
                        cw  = sum(1 for t in ct if t["pnl_pts"] > 0)
                        cl  = sum(1 for t in ct if t["pnl_pts"] < 0)
                        cbe = sum(1 for t in ct if t["pnl_pts"] == 0)
                        cpnl = sum(t["pnl_pts"] for t in ct)
                        cgw = sum(t["pnl_pts"] for t in ct if t["pnl_pts"] > 0)
                        cgl = sum(t["pnl_pts"] for t in ct if t["pnl_pts"] < 0)
                        cpf = abs(cgw / cgl) if cgl else float("inf")
                        cat_rows.append({
                            "Signal":      name,
                            "Trades":      len(ct),
                            "W/L/BE":      f"{cw}/{cl}/{cbe}",
                            "Win %":       f"{cw/len(ct)*100:.1f}%",
                            "Total Pts":   f"{cpnl:+,.0f}",
                            "Avg/Trade":   f"{cpnl/len(ct):+.1f}",
                            "Profit Factor": f"{cpf:.2f}" if cpf != float("inf") else "∞",
                            "Avg R":       f"{sum(t['r_mult'] for t in ct)/len(ct):+.2f}",
                        })
                    if cat_rows:
                        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

                    # Detailed trade log
                    with st.expander(f"📋 Detailed trade log ({len(trades)} trades)"):
                        log_rows = []
                        status_label = {"sl": "🔴 SL", "be": "⚪ BE", "trail": "🟢 Trail", "open": "🟡 Open"}
                        for t in reversed(trades):
                            hours_held = (t["exit_dt"] - t["entry_dt"]).total_seconds() / 3600
                            log_rows.append({
                                "Signal Time":  t["signal_dt"].strftime("%d %b %H:%M"),
                                "Side":         "🟢 Buy" if t["side"] == "buy" else "🔴 Sell",
                                "Type":         t["label"],
                                "Entry":        f"{t['entry']:,.1f}",
                                "SL (pts)":     f"{t['sl_pts']:.0f}",
                                "Exit":         f"{t['exit']:,.1f}",
                                "Outcome":      status_label.get(t["status"], t["status"]),
                                "P&L (pts)":    t["pnl_pts"],
                                "R":            t["r_mult"],
                                "Held":         f"{hours_held:.0f}h" if hours_held < 48 else f"{hours_held/24:.1f}d",
                            })
                        df_log = pd.DataFrame(log_rows)

                        def _col_pnl(v):
                            if v is None or (isinstance(v, float) and pd.isna(v)): return ""
                            return f"color: {GREEN}" if v > 0 else (f"color: {RED}" if v < 0 else f"color: {MUTED}")

                        styled_log = (
                            df_log.style
                            .map(_col_pnl, subset=["P&L (pts)", "R"])
                            .format({"P&L (pts)": lambda v: f"{v:+.1f}", "R": lambda v: f"{v:+.2f}"})
                        )
                        st.dataframe(styled_log, use_container_width=True, hide_index=True, height=400)

                    interp("**How to read this:** Low win-rate but high profit-factor systems work because the **trail** captures the rare big runners. "
                           "The 60-pt SL→BE→trail rule sacrifices many would-be wins to scratches (the 'BE' bucket), but protects you from giving back gains. "
                           "If profit factor > 1.5, the math is in your favour over a large sample. Slippage and brokerage will eat ~2-3 pts per trade — factor that in.")
            else:
                st.info("No 1H intraday signals in the last 60 days with current sensitivity settings.")
        else:
            no_data("1H data not fetched yet — click ⟳ Refresh to pull via yfinance")

else:
    no_data("Nifty chart data not fetched yet — click ⟳ Refresh")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET HEALTH — VIX + BREADTH
# ═══════════════════════════════════════════════════════════════════════════════

sec("MARKET HEALTH", "🏥")

col_vix, col_ad = st.columns(2)

with col_vix:
    if df_vix is not None:
        vcol = next((c for c in df_vix.columns if "close" in c.lower() or "vix" in c.lower()), df_vix.columns[-1])
        dcol = next((c for c in df_vix.columns if "date" in c.lower() or "time" in c.lower()), df_vix.columns[0])
        df_vix[vcol] = pd.to_numeric(df_vix[vcol], errors="coerce")
        df_vix = df_vix.dropna(subset=[vcol]).tail(30)
        vix_now = df_vix[vcol].iloc[-1]
        vix_prev = df_vix[vcol].iloc[-2]
        vix_chg = vix_now - vix_prev

        if vix_now < 14:   vlbl, vcls = "COMPLACENT", "badge-bull"
        elif vix_now < 18: vlbl, vcls = "CALM",        "badge-bull"
        elif vix_now < 22: vlbl, vcls = "CAUTION",     "badge-flat"
        elif vix_now < 27: vlbl, vcls = "FEAR",        "badge-bear"
        else:              vlbl, vcls = "PANIC",        "badge-bear"

        vdir = "▲" if vix_chg >= 0 else "▼"
        vc   = RED if vix_chg >= 0 else GREEN
        st.markdown(f"""
        <div class="stat-card">
          <div class="stat-label">India VIX &nbsp; <span class="{vcls}">{vlbl}</span></div>
          <div class="stat-value">{vix_now:.2f}
            <span style="font-size:0.95rem;color:{vc};font-weight:600">&nbsp;{vdir} {abs(vix_chg):.2f}</span>
          </div>
          <div class="stat-sub">Fear gauge — rising VIX = danger, falling = calm</div>
        </div>""", unsafe_allow_html=True)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_vix[dcol], y=df_vix[vcol],
            fill="tozeroy", fillcolor="rgba(80,134,234,0.10)",
            line=dict(color=BLUE, width=2), name="VIX",
        ))
        for level, lbl, col in [(14, "Calm", GREEN), (18, "Caution", YELLOW), (22, "Fear", "#f09030"), (27, "Panic", RED)]:
            fig.add_hline(y=level, line_dash="dot", line_color=col, opacity=0.5,
                         annotation_text=lbl, annotation_position="right",
                         annotation=dict(font=dict(size=9, color=col)))
        plo_layout(fig, "India VIX — 30 Day", height=220, show_legend=False)
        st.plotly_chart(fig, use_container_width=True)

        if vix_chg > 0.5:
            interp("VIX is rising — market fear is increasing. Reduce position sizes, avoid OTM options buying.")
        elif vix_chg < -0.5:
            interp("VIX falling — fear is easing. Good environment for directional trades.")
    else:
        no_data()

with col_ad:
    if df_ad is not None and not df_ad.empty:
        lat = df_ad.iloc[-1]
        adv, dec = int(lat["advances"]), int(lat["declines"])
        ratio = adv / max(dec, 1)

        if ratio > 2.5:   albl, acls = "STRONG BREADTH", "badge-bull"
        elif ratio > 1.3: albl, acls = "POSITIVE BREADTH", "badge-bull"
        elif ratio > 0.7: albl, acls = "MIXED BREADTH",  "badge-flat"
        else:             albl, acls = "NEGATIVE BREADTH", "badge-bear"

        st.markdown(f"""
        <div class="stat-card">
          <div class="stat-label">Advance / Decline &nbsp; <span class="{acls}">{albl}</span></div>
          <div class="stat-value">
            <span class="up">{adv}</span>
            <span style="color:{MUTED};font-size:1rem;font-weight:400"> / </span>
            <span class="down">{dec}</span>
          </div>
          <div class="stat-sub">A/D ratio {ratio:.2f} &nbsp;·&nbsp; {lat['unchanged']} unchanged</div>
        </div>""", unsafe_allow_html=True)

        fig = go.Figure()
        df_ad["advances"] = pd.to_numeric(df_ad["advances"], errors="coerce")
        df_ad["declines"] = pd.to_numeric(df_ad["declines"], errors="coerce")
        fig.add_trace(go.Bar(x=df_ad["date"], y=df_ad["advances"],  name="Advances", marker_color=GREEN, opacity=0.9))
        fig.add_trace(go.Bar(x=df_ad["date"], y=-df_ad["declines"], name="Declines",  marker_color=RED,   opacity=0.9))
        fig.update_layout(barmode="overlay")
        plo_layout(fig, "Breadth — Last 5 Days", height=220)
        st.plotly_chart(fig, use_container_width=True)

        if ratio > 2:
            interp(f"Strong breadth — {adv} stocks up vs {dec} down. Rally is broad-based, not just index heavyweights.")
        elif ratio < 0.6:
            interp(f"Weak breadth — only {adv} stocks advancing. Selling is widespread. Avoid catching falling knives.")
        else:
            interp("Mixed breadth — no clear bias. Stock picking matters more than index direction today.")
    else:
        no_data()

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR ROTATION
# ═══════════════════════════════════════════════════════════════════════════════

sec("SECTOR ROTATION", "🔄")

if df_indices is not None and "percentChange" in df_indices.columns:
    df_indices["percentChange"] = pd.to_numeric(df_indices["percentChange"], errors="coerce")
    sector_kw = ["NIFTY BANK", "NIFTY IT", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY FMCG",
                 "NIFTY METAL", "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA", "NIFTY MEDIA",
                 "PSU BANK", "MIDCAP IT", "MIDSMALL", "HEALTHCARE", "CONSUMER DURABLES",
                 "OIL", "FINANCIAL SERVICES", "COMMODITIES", "PRIVATE BANK"]
    mask = df_indices["index"].str.upper().apply(lambda x: any(k in str(x) for k in sector_kw))
    df_sec = df_indices[mask].dropna(subset=["percentChange"]).sort_values("percentChange", ascending=True)

    if not df_sec.empty:
        top3_bull = df_sec[df_sec["percentChange"] > 0].tail(3)["index"].tolist()
        top3_bear = df_sec[df_sec["percentChange"] < 0].head(3)["index"].tolist()
        green_count = (df_sec["percentChange"] > 0).sum()
        total_count = len(df_sec)

        fig = go.Figure(go.Bar(
            x=df_sec["percentChange"],
            y=df_sec["index"],
            orientation="h",
            marker_color=[GREEN if v >= 0 else RED for v in df_sec["percentChange"]],
            text=[f"{v:+.2f}%" for v in df_sec["percentChange"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig.update_layout(
            yaxis=dict(tickfont=dict(size=10)),
            xaxis=dict(ticksuffix="%"),
        )
        plo_layout(fig, "Today's Sector Performance", height=max(380, len(df_sec) * 26))
        st.plotly_chart(fig, use_container_width=True)

        bull_txt = ", ".join(top3_bull) if top3_bull else "none"
        bear_txt = ", ".join(top3_bear) if top3_bear else "none"
        interp(f"**{green_count}/{total_count} sectors positive today.** "
               f"Money flowing into: {bull_txt}. "
               f"Selling pressure in: {bear_txt}. "
               f"{'Rotate into leaders and avoid laggards.' if green_count > total_count/2 else 'Defensive posture — broad sector weakness.'}")
else:
    no_data()

# Heatmap
if df_sh is not None:
    idx_col_sh = "index_name" if "index_name" in df_sh.columns else "INDEX_NAME"
    date_col_sh = "TIMESTAMP" if "TIMESTAMP" in df_sh.columns else None
    close_col_sh = "CLOSE_INDEX_VAL" if "CLOSE_INDEX_VAL" in df_sh.columns else None
    if date_col_sh and close_col_sh and idx_col_sh in df_sh.columns:
        df_sh[close_col_sh] = pd.to_numeric(df_sh[close_col_sh], errors="coerce")
        parts = []
        for name, grp in df_sh.groupby(idx_col_sh):
            grp = grp.sort_values(date_col_sh).copy()
            grp["ret"] = grp[close_col_sh].pct_change() * 100
            parts.append(grp)
        if parts:
            df_pct = pd.concat(parts, ignore_index=True)
            pivot = df_pct.pivot_table(index=idx_col_sh, columns=date_col_sh, values="ret")
            pivot = pivot.iloc[:, -15:]
            fig2 = go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0, RED], [0.5, SURFACE2], [1, GREEN]],
                zmid=0,
                text=np.round(pivot.values, 1),
                texttemplate="%{text}%",
                textfont=dict(size=9),
                hovertemplate="%{y}<br>%{x}<br>%{z:.2f}%<extra></extra>",
            ))
            plo_layout(fig2, "Sector Rotation Heatmap — Daily Returns (Last 15 Sessions)", height=420)
            st.plotly_chart(fig2, use_container_width=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# FII / DII ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════

sec("FII / DII ACTIVITY", "🌍")

if df_fiidii is not None and "netValue" in df_fiidii.columns:
    df_fiidii["buyValue"]  = pd.to_numeric(df_fiidii["buyValue"],  errors="coerce")
    df_fiidii["sellValue"] = pd.to_numeric(df_fiidii["sellValue"], errors="coerce")
    df_fiidii["netValue"]  = pd.to_numeric(df_fiidii["netValue"],  errors="coerce")

    fii_row = df_fiidii[df_fiidii["category"].str.contains("FII|FPI", na=False, case=False)]
    dii_row = df_fiidii[df_fiidii["category"].str.contains("DII",     na=False, case=False)]

    fii_net = fii_row["netValue"].iloc[-1] if not fii_row.empty else 0
    dii_net = dii_row["netValue"].iloc[-1] if not dii_row.empty else 0
    fii_col = GREEN if fii_net >= 0 else RED
    dii_col = GREEN if dii_net >= 0 else RED

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(stat_card("FII/FPI Net",  fmt_cr(fii_net), "Today", fii_col), unsafe_allow_html=True)
    c2.markdown(stat_card("DII Net",      fmt_cr(dii_net), "Today", dii_col), unsafe_allow_html=True)
    if not fii_row.empty:
        c3.markdown(stat_card("FII Buy",  f"₹{fii_row['buyValue'].iloc[-1]:,.0f} Cr",  "", MUTED), unsafe_allow_html=True)
        c4.markdown(stat_card("FII Sell", f"₹{fii_row['sellValue'].iloc[-1]:,.0f} Cr", "", MUTED), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Interpretation
    if fii_net > 500 and dii_net > 0:
        interp(f"Both FIIs (+₹{fii_net:,.0f} Cr) and DIIs (+₹{dii_net:,.0f} Cr) are net buyers — **double confirmation** of institutional buying. Strong signal for longs.")
    elif fii_net > 0 and dii_net < 0:
        interp(f"FIIs buying (+₹{fii_net:,.0f} Cr) but DIIs selling (₹{dii_net:,.0f} Cr) — domestic MFs may be taking profits. Net positive but watch for selling on rallies.")
    elif fii_net < -500:
        interp(f"FIIs net sellers (₹{fii_net:,.0f} Cr) — foreign money is exiting. Avoid aggressive longs; wait for FII flow to stabilize before entering.")
    else:
        interp("FII/DII flows are modest today. No strong directional signal from institutional activity.")

    with st.expander("Full FII/DII Table"):
        st.dataframe(df_fiidii, use_container_width=True, hide_index=True)
else:
    no_data()

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# F&O PARTICIPANT OI + FII DERIVATIVES
# ═══════════════════════════════════════════════════════════════════════════════

sec("F&O PARTICIPANT OPEN INTEREST — WHO IS DOING WHAT", "📊")

st.markdown(f"""
<div style="background:{SURFACE2};border-radius:10px;padding:1rem 1.2rem;margin-bottom:1rem;
            border-left:3px solid {YELLOW};font-size:0.8rem;color:{TEXT};line-height:1.8">
  <b style="color:{YELLOW}">How to read this correctly:</b><br>
  • <b>Index Futures</b> = the ONLY clean directional signal. Long futures = betting market goes UP. Short futures = betting it goes DOWN.<br>
  • <b>Options (calls & puts)</b> = <em>not directly directional</em>. Selling a call AND selling a put both look like "shorts" but mean very different things.
    What matters is: <em>are they buying puts</em> (bearish hedge) or <em>buying calls</em> (bullish bet)?<br>
  • <b>Rule of thumb:</b> Follow FII <em>Index Futures</em> for market direction. Use Options net-buying to confirm the bias.
</div>
""", unsafe_allow_html=True)

if df_poi is not None and not df_poi.empty:
    # Numeric-ify all OI columns
    oi_cols = [c for c in df_poi.columns if c != "Client Type"]
    for c in oi_cols:
        df_poi[c] = pd.to_numeric(df_poi[c], errors="coerce")

    df_data = df_poi[df_poi["Client Type"] != "TOTAL"].copy()

    def get_row(cat_keyword):
        mask = df_data["Client Type"].str.upper().str.contains(cat_keyword, na=False)
        return df_data[mask].iloc[0] if mask.any() else None

    fii_row    = get_row("FII")
    client_row = get_row("CLIENT")
    dii_row    = get_row("DII")
    pro_row    = get_row("PRO")

    # ── PART 1: INDEX FUTURES — directional ──────────────────────────────────
    st.markdown(f'<div class="sec-head" style="font-size:0.72rem">📍 INDEX FUTURES — DIRECTIONAL SIGNAL</div>', unsafe_allow_html=True)

    fut_cats = {}
    for label, row in [("FII", fii_row), ("Client (Retail)", client_row), ("DII", dii_row), ("Pro/HNI", pro_row)]:
        if row is not None:
            fl = row.get("Future Index Long", 0) or 0
            fs = row.get("Future Index Short", 0) or 0
            net = fl - fs
            fut_cats[label] = {"long": fl, "short": fs, "net": net}

    if fut_cats:
        cols_fut = st.columns(len(fut_cats))
        for i, (label, v) in enumerate(fut_cats.items()):
            net = v["net"]
            nc  = GREEN if net > 0 else RED
            bias = "LONG" if net > 0 else "SHORT"
            cols_fut[i].markdown(f"""
            <div class="stat-card" style="border-top: 3px solid {nc}">
              <div class="stat-label">{label}</div>
              <div class="stat-value" style="color:{nc};font-size:1.1rem">{bias}</div>
              <div class="stat-sub">
                Net: <b style="color:{nc}">{net:+,.0f}</b> contracts<br>
                Long {v['long']:,.0f} · Short {v['short']:,.0f}
              </div>
            </div>""", unsafe_allow_html=True)

        # Net futures bar chart
        fig_fut = go.Figure()
        labels  = list(fut_cats.keys())
        nets    = [v["net"] for v in fut_cats.values()]
        colors  = [GREEN if n > 0 else RED for n in nets]
        fig_fut.add_trace(go.Bar(
            x=labels, y=nets,
            marker_color=colors,
            text=[f"{n:+,.0f}" for n in nets],
            textposition="outside",
            textfont=dict(size=11),
        ))
        fig_fut.add_hline(y=0, line_color=MUTED, line_width=1)
        plo_layout(fig_fut, "Net Index Futures Position (Long − Short contracts)", height=240, show_legend=False)
        fig_fut.update_layout(yaxis_title="Net Contracts")
        st.plotly_chart(fig_fut, use_container_width=True)

        # Directional interpretation
        fii_net_fut = fut_cats.get("FII", {}).get("net", 0)
        cli_net_fut = fut_cats.get("Client (Retail)", {}).get("net", 0)
        if fii_net_fut < -50000 and cli_net_fut > 50000:
            interp(f"**Classic FII vs Retail divergence.** FIIs are net SHORT ({fii_net_fut:+,.0f} contracts) while retail is net LONG ({cli_net_fut:+,.0f}). "
                   f"Historically this is **bearish** — smart money is positioned against the crowd. Avoid fresh index longs.")
        elif fii_net_fut > 50000:
            interp(f"FIIs are net LONG in index futures ({fii_net_fut:+,.0f} contracts) — they're putting real money behind an up-move. "
                   f"This is a strong bullish signal. Favour buying dips.")
        elif fii_net_fut < 0:
            interp(f"FIIs are net SHORT in index futures ({fii_net_fut:+,.0f} contracts) — they're either hedging or betting on a down-move. "
                   f"Be cautious with fresh longs. Wait for FII net to flip positive before adding.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PART 2: INDEX OPTIONS — sentiment ────────────────────────────────────
    st.markdown(f'<div class="sec-head" style="font-size:0.72rem">📍 INDEX OPTIONS — SENTIMENT SIGNAL</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div style="font-size:0.75rem;color:{MUTED};margin-bottom:0.8rem;line-height:1.6">
      <b style="color:{TEXT}">Net Call buying</b> = Call Long − Call Short.
      Positive → they expect market to go UP.
      <b style="color:{TEXT}">Net Put buying</b> = Put Long − Put Short.
      Positive → they're buying downside protection (BEARISH/hedge).
    </div>""", unsafe_allow_html=True)

    opt_summary = []
    for label, row in [("FII", fii_row), ("Client (Retail)", client_row), ("DII", dii_row), ("Pro/HNI", pro_row)]:
        if row is not None:
            net_call = (row.get("Option Index Call Long", 0) or 0) - (row.get("Option Index Call Short", 0) or 0)
            net_put  = (row.get("Option Index Put Long",  0) or 0) - (row.get("Option Index Put Short",  0) or 0)
            # Bias: net_call positive = bullish, net_put positive = bearish
            bias_score = net_call - net_put
            if bias_score > 100000:   bias, bc = "BULLISH",  GREEN
            elif bias_score > 0:      bias, bc = "Mildly Bull", "#7ec8a0"
            elif bias_score > -100000: bias, bc = "Mildly Bear", "#f0a070"
            else:                     bias, bc = "BEARISH",  RED
            opt_summary.append({"Category": label, "Net Call Buying": net_call,
                                 "Net Put Buying": net_put, "Bias": bias, "_bc": bc, "_score": bias_score})

    if opt_summary:
        opt_cols = st.columns(len(opt_summary))
        for i, row in enumerate(opt_summary):
            opt_cols[i].markdown(f"""
            <div class="stat-card" style="border-top: 3px solid {row['_bc']}">
              <div class="stat-label">{row['Category']}</div>
              <div class="stat-value" style="color:{row['_bc']};font-size:1.0rem">{row['Bias']}</div>
              <div class="stat-sub">
                Net Calls: <b style="color:{'#22ab94' if row['Net Call Buying']>0 else '#eb5757'}">{row['Net Call Buying']:+,.0f}</b><br>
                Net Puts:  <b style="color:{'#eb5757' if row['Net Put Buying']>0 else '#22ab94'}">{row['Net Put Buying']:+,.0f}</b>
              </div>
            </div>""", unsafe_allow_html=True)

        # Options bias chart
        fig_opt = go.Figure()
        cats    = [r["Category"] for r in opt_summary]
        fig_opt.add_trace(go.Bar(name="Net Call Buying (bullish →)",
                                  x=cats, y=[r["Net Call Buying"] for r in opt_summary],
                                  marker_color=GREEN, opacity=0.85))
        fig_opt.add_trace(go.Bar(name="Net Put Buying (bearish →)",
                                  x=cats, y=[r["Net Put Buying"] for r in opt_summary],
                                  marker_color=RED, opacity=0.85))
        fig_opt.add_hline(y=0, line_color=MUTED, line_width=1)
        fig_opt.update_layout(barmode="group")
        plo_layout(fig_opt, "Index Options: Net Call vs Net Put Buying", height=240)
        st.plotly_chart(fig_opt, use_container_width=True)

        fii_opt = next((r for r in opt_summary if r["Category"] == "FII"), None)
        if fii_opt:
            if fii_opt["Net Put Buying"] > 200000:
                interp(f"FIIs have bought {fii_opt['Net Put Buying']:,.0f} more puts than they've sold — "
                       f"they're actively hedging against a fall. This **confirms the bearish index futures position**. "
                       f"Both signals point down: avoid index longs, consider buying puts on rallies.")
            elif fii_opt["Net Call Buying"] > 200000:
                interp(f"FIIs are net buyers of calls ({fii_opt['Net Call Buying']:,.0f} contracts) — "
                       f"they're making a directional bullish bet via options. Supports index longs.")
            else:
                interp("FII options positioning is mixed — no strong directional signal from options alone. Focus on the index futures net position above.")

    with st.expander("Raw participant OI data"):
        st.dataframe(df_poi, use_container_width=True, hide_index=True)

else:
    no_data()

st.markdown("<br>", unsafe_allow_html=True)

# FII Derivatives (index futures stats from NSE)
if df_fiider is not None and not df_fiider.empty:
    with st.expander("FII Derivatives Statistics (NSE official — buy/sell by product)"):
        st.dataframe(df_fiider, use_container_width=True, hide_index=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# BULK & BLOCK DEALS
# ═══════════════════════════════════════════════════════════════════════════════

sec("BULK & BLOCK DEALS", "💼")

tab_bulk, tab_block = st.tabs(["Bulk Deals", "Block Deals"])

with tab_bulk:
    if df_bulk is not None:
        qty_col = next((c for c in df_bulk.columns if "qty" in c.lower() or "quant" in c.lower()), None)
        prc_col = next((c for c in df_bulk.columns if "price" in c.lower()), None)
        sym_col = next((c for c in df_bulk.columns if "symbol" in c.lower()), None)
        bs_col  = next((c for c in df_bulk.columns if "buy" in c.lower() or "sell" in c.lower() or "b_s" in c.lower()), None)

        if qty_col and prc_col and sym_col:
            df_bulk[qty_col] = pd.to_numeric(df_bulk[qty_col], errors="coerce")
            df_bulk[prc_col] = pd.to_numeric(df_bulk[prc_col], errors="coerce")
            df_bulk["deal_value_cr"] = (df_bulk[qty_col] * df_bulk[prc_col]) / 1e7
            cols_show = [sym_col, bs_col, qty_col, prc_col, "deal_value_cr"] if bs_col else [sym_col, qty_col, prc_col, "deal_value_cr"]
            top = df_bulk.nlargest(20, "deal_value_cr")[cols_show]
            st.dataframe(top, use_container_width=True, hide_index=True)
            interp(f"{len(df_bulk)} bulk deals in the last week. "
                   + (f"Biggest: **{top[sym_col].iloc[0]}** — ₹{top['deal_value_cr'].iloc[0]:,.0f} Cr." if len(top) > 0 else ""))
        else:
            st.dataframe(df_bulk.head(25), use_container_width=True, hide_index=True)
    else:
        no_data()

with tab_block:
    if df_block is not None:
        st.dataframe(df_block, use_container_width=True, hide_index=True)
        interp("Block deals are large pre-negotiated trades between institutions — strong directional conviction signal.")
    else:
        no_data()

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH DELIVERY % STOCKS
# ═══════════════════════════════════════════════════════════════════════════════

sec("HIGH DELIVERY % STOCKS — NIFTY 500", "📦")

if df_hd is not None and not df_hd.empty:
    c1, c2 = st.columns([3, 1])
    with c1:
        def color_del(v):
            try:
                return f"color: {GREEN}" if float(v) >= 70 else (f"color: {YELLOW}" if float(v) >= 60 else "")
            except Exception:
                return ""
        st.dataframe(
            df_hd.style.applymap(color_del, subset=["avg_delivery_pct"]),
            use_container_width=True, height=380, hide_index=True,
        )
    with c2:
        st.markdown(stat_card("Qualifying Stocks", str(len(df_hd)), "Avg delivery >60% / 10 days", GREEN), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(stat_card("Very Strong (>75%)", str(len(df_hd[df_hd["avg_delivery_pct"] >= 75])), "Sustained accumulation", GREEN), unsafe_allow_html=True)
    interp("High delivery % means real buying — shares are being held, not just traded intraday. "
           "Stocks consistently above 60% delivery for 10 days signal **institutional accumulation**. "
           "These are positional candidates — wait for a price breakout or pullback to enter.")
else:
    no_data("High delivery screener runs as part of the 7 PM EOD fetch (takes ~15 min for 500 stocks).")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# INTRADAY SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

sec("INTRADAY SIGNALS", "⚡")

tab_52, tab_act, tab_gl = st.tabs(["52-Week Highs/Lows", "Most Active", "Gainers & Losers"])

with tab_52:
    if df_52 is not None:
        cols_52 = df_52.columns.tolist()
        sym52 = next((c for c in cols_52 if "symbol" in c.lower()), None)
        cl52  = st.columns(2)
        with cl52[0]:
            st.markdown(f'<span class="badge-bull">52W HIGHS — Momentum plays</span>', unsafe_allow_html=True)
            high_col = next((c for c in cols_52 if "new" in c.lower() and "high" in c.lower()), None)
            df_highs = df_52[df_52[high_col].notna()].head(20) if high_col else df_52.head(20)
            st.dataframe(df_highs, use_container_width=True, hide_index=True, height=340)
        with cl52[1]:
            st.markdown(f'<span class="badge-bear">52W LOWS — Avoid or watch reversal</span>', unsafe_allow_html=True)
            low_col = next((c for c in cols_52 if "new" in c.lower() and "low" in c.lower()), None)
            df_lows = df_52[df_52[low_col].notna()].head(20) if low_col else df_52.tail(20)
            st.dataframe(df_lows, use_container_width=True, hide_index=True, height=340)
        interp("Stocks making 52-week highs have the market's backing — momentum is on your side. "
               "Stocks at 52-week lows are in downtrends — only trade them with very tight risk parameters.")
    else:
        no_data()

with tab_act:
    ca1, ca2 = st.columns(2)
    with ca1:
        if df_mav is not None:
            st.caption("Most Active by Value")
            st.dataframe(df_mav, use_container_width=True, hide_index=True, height=360)
        else: no_data()
    with ca2:
        if df_mavol is not None:
            st.caption("Most Active by Volume")
            st.dataframe(df_mavol, use_container_width=True, hide_index=True, height=360)
        else: no_data()
    interp("High-value stocks are the institutional playground — follow the money. High-volume but low-value stocks are retail-driven.")

with tab_gl:
    cg1, cg2 = st.columns(2)
    with cg1:
        if df_g is not None:
            st.markdown(f'<span class="badge-bull">TOP GAINERS</span>', unsafe_allow_html=True)
            st.dataframe(df_g, use_container_width=True, hide_index=True, height=360)
        else: no_data()
    with cg2:
        if df_l is not None:
            st.markdown(f'<span class="badge-bear">TOP LOSERS</span>', unsafe_allow_html=True)
            st.dataframe(df_l, use_container_width=True, hide_index=True, height=360)
        else: no_data()

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# POSITIONAL WATCH
# ═══════════════════════════════════════════════════════════════════════════════

sec("POSITIONAL WATCH — INSTITUTIONAL ACCUMULATION CANDIDATES", "🎯")

if df_hd is not None and not df_hd.empty:
    positional = df_hd[df_hd["avg_delivery_pct"] >= 65].copy()

    bulk_syms  = set(df_bulk[next((c for c in df_bulk.columns if "symbol" in c.lower()), df_bulk.columns[0])].str.upper().dropna()) if df_bulk is not None else set()
    block_syms = set(df_block[next((c for c in df_block.columns if "symbol" in c.lower()), df_block.columns[0])].str.upper().dropna()) if df_block is not None else set()

    if "symbol" in positional.columns:
        positional["bulk_deal"]  = positional["symbol"].str.upper().isin(bulk_syms).map({True: "✅", False: ""})
        positional["block_deal"] = positional["symbol"].str.upper().isin(block_syms).map({True: "✅", False: ""})
        positional["conviction"] = positional["avg_delivery_pct"].apply(
            lambda x: "🔥 Very High" if x >= 75 else "✅ High"
        )

    p1, p2, p3 = st.columns([3, 1, 1])
    with p1:
        st.dataframe(positional, use_container_width=True, hide_index=True, height=360)
    with p2:
        st.markdown(stat_card("Total Candidates", str(len(positional)), "Avg delivery ≥65%", GREEN), unsafe_allow_html=True)
    with p3:
        also_bulk = positional[positional.get("bulk_deal", pd.Series([""] * len(positional))) == "✅"] if "bulk_deal" in positional.columns else pd.DataFrame()
        st.markdown(stat_card("Also in Bulk Deals", str(len(also_bulk)), "Double confirmation", GREEN), unsafe_allow_html=True)

    interp("These stocks show sustained institutional accumulation. Best entry: **on a pullback to support** or **on a volume breakout above recent highs**. "
           "Stocks marked ✅ in both delivery AND bulk/block deals have triple confirmation — highest conviction trades.")
else:
    no_data("Positional watch requires the EOD delivery screener (runs at 7 PM — takes ~15 min).")


# ── Footer & Disclaimer ──────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:3rem;padding:1.4rem 1.6rem;border:1px solid {BORDER};border-radius:10px;background:rgba(247,186,80,0.04)">
  <div style="font-size:0.78rem;font-weight:600;color:{YELLOW};margin-bottom:0.5rem">⚠️ DISCLAIMER</div>
  <div style="font-size:0.72rem;color:{TEXT};line-height:1.6">
    This dashboard is for <b>educational and informational purposes only</b>. It is <b>not</b> investment advice,
    a recommendation, or a solicitation to buy or sell any security. The signals shown are derived from public
    NSE data and are <b>not guarantees of future performance</b>. Past performance does not predict future results.
    The author is <b>not a SEBI-registered investment advisor</b>. Trading in equity and derivatives involves
    substantial risk of loss. Always do your own research and consult a SEBI-registered advisor before making
    investment decisions. By using this site you agree that the author bears no responsibility for any trading
    decisions or losses incurred.
  </div>
</div>
<div style="text-align:center;color:{MUTED};font-size:0.68rem;padding:1.2rem 0 0.5rem">
  Data sources: NSE India (nselib) · Yahoo Finance (1H bars) &nbsp;·&nbsp;
  Refresh: 9 AM pre-market, 7 PM EOD (IST) &nbsp;·&nbsp;
  <a href="https://github.com/" style="color:{MUTED};text-decoration:none">View source on GitHub</a>
</div>
""", unsafe_allow_html=True)
