"""
NSE Dashboard Data Fetcher
Pulls all required data from NSE via nselib and saves to ~/nse-dashboard/data/
Run at 7 PM (EOD) and 9 AM (pre-market) on weekdays via LaunchAgent.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from nselib import capital_market, derivatives, indices

# nselib 2.5.1 forgot to export `fii_dii_trading_activity` in capital_market/__init__.py.
# Fall back to the submodule import so the code works with stock nselib (e.g., on Streamlit Cloud).
if not hasattr(capital_market, "fii_dii_trading_activity"):
    try:
        from nselib.capital_market.capital_market_data import fii_dii_trading_activity
        capital_market.fii_dii_trading_activity = fii_dii_trading_activity
    except ImportError:
        pass

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "fetcher.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

SECTORAL_INDICES = [
    "NIFTY BANK", "NIFTY IT", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY FMCG",
    "NIFTY METAL", "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA", "NIFTY MEDIA",
    "NIFTY PSU BANK", "NIFTY MIDCAP IT & TELECOM", "NIFTY HEALTHCARE INDEX",
    "NIFTY CONSUMER DURABLES", "NIFTY OIL & GAS", "NIFTY FINANCIAL SERVICES",
    "NIFTY COMMODITIES", "NIFTY PRIVATE BANK",
]


def save(name: str, df: pd.DataFrame):
    path = DATA_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    log.info(f"Saved {name}.csv ({len(df)} rows)")


def archive_save(name: str, df: pd.DataFrame, dedupe_on: str):
    """
    Append-and-dedupe save: merges new data with existing CSV, keeping the LATEST
    values for duplicate keys. Lets the data archive grow beyond what the source API returns
    (e.g., yfinance only gives 60d of 1H, but archive keeps everything ever fetched).
    """
    path = DATA_DIR / f"{name}.csv"
    if path.exists() and dedupe_on in df.columns:
        try:
            existing = pd.read_csv(path)
            if dedupe_on in existing.columns:
                combined = pd.concat([existing, df], ignore_index=True)
                # keep="last" → today's re-fetch overwrites stale rows
                combined = combined.drop_duplicates(subset=[dedupe_on], keep="last")
                # Sort by the dedupe column if it's parseable as a date
                try:
                    combined["_sort"] = pd.to_datetime(combined[dedupe_on], errors="coerce")
                    combined = combined.sort_values("_sort").drop(columns=["_sort"])
                except Exception:
                    pass
                df = combined.reset_index(drop=True)
        except Exception as e:
            log.warning(f"Archive merge failed for {name}: {e}; overwriting")
    df.to_csv(path, index=False)
    log.info(f"Archived {name}.csv ({len(df)} rows total)")


def save_meta(key: str, value):
    meta_path = DATA_DIR / "meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    meta[key] = value
    meta_path.write_text(json.dumps(meta, indent=2))


def last_n_trading_dates(n: int) -> list[str]:
    """Return last n weekdays as dd-mm-YYYY strings, excluding today if before 6 PM."""
    dates = []
    d = datetime.now().date()
    # If before 6 PM, yesterday is the last trading day
    if datetime.now().hour < 18:
        d -= timedelta(days=1)
    while len(dates) < n:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d.strftime("%d-%m-%Y"))
        d -= timedelta(days=1)
    return dates


def today_trade_date() -> str:
    d = datetime.now().date()
    if datetime.now().hour < 18:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%d-%m-%Y")


def fetch_with_retry(fn, *args, retries=3, delay=5, **kwargs):
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log.warning(f"{fn.__name__} attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    log.error(f"{fn.__name__} failed after {retries} attempts")
    return None


# ── Market Health ─────────────────────────────────────────────────────────────

def fetch_vix():
    df = fetch_with_retry(capital_market.india_vix_data, period="1M")
    if df is not None:
        archive_save("vix", df, dedupe_on="TIMESTAMP")


def fetch_advance_decline():
    """Derive advance/decline from bhav copy for last 5 days."""
    rows = []
    for date_str in last_n_trading_dates(5):
        try:
            bhav = capital_market.bhav_copy_with_delivery(trade_date=date_str)
            if bhav is not None and not bhav.empty:
                # Close vs PrevClose gives advance/decline
                if "CH_CLOSING_PRICE" in bhav.columns and "CH_PREVIOUS_CLS_PRICE" in bhav.columns:
                    advances = (bhav["CH_CLOSING_PRICE"] > bhav["CH_PREVIOUS_CLS_PRICE"]).sum()
                    declines = (bhav["CH_CLOSING_PRICE"] < bhav["CH_PREVIOUS_CLS_PRICE"]).sum()
                    unchanged = (bhav["CH_CLOSING_PRICE"] == bhav["CH_PREVIOUS_CLS_PRICE"]).sum()
                    rows.append({"date": date_str, "advances": int(advances),
                                 "declines": int(declines), "unchanged": int(unchanged)})
        except Exception as e:
            log.warning(f"Advance/Decline for {date_str}: {e}")
    if rows:
        save("advance_decline", pd.DataFrame(rows))


# ── Sector Rotation ───────────────────────────────────────────────────────────

def fetch_sector_performance():
    df = fetch_with_retry(capital_market.market_watch_all_indices)
    if df is not None:
        save("all_indices", df)

    # Also pull 5-day history for each sectoral index for rotation chart
    rows = []
    for idx in SECTORAL_INDICES:
        try:
            hist = capital_market.index_data(index=idx, period="1M")
            if hist is not None and not hist.empty:
                hist["index_name"] = idx
                rows.append(hist)
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"Sector history {idx}: {e}")
    if rows:
        save("sector_history", pd.concat(rows, ignore_index=True))


# ── FII / DII Activity ────────────────────────────────────────────────────────

def fetch_fii_dii():
    df = fetch_with_retry(capital_market.fii_dii_trading_activity)
    if df is not None:
        # Dedupe on (date, category) — use a composite key
        df["_key"] = df["date"].astype(str) + "|" + df["category"].astype(str)
        archive_save("fii_dii", df, dedupe_on="_key")
        # Drop the helper key column on disk
        path = DATA_DIR / "fii_dii.csv"
        out = pd.read_csv(path).drop(columns=["_key"], errors="ignore")
        out.to_csv(path, index=False)


# ── Nifty 1H OHLC (yfinance, for intraday zone-touch signals) ────────────────

def fetch_nifty_1h():
    """Fetch 1H Nifty 50 data via yfinance (last 60 days). No resampling — keep native 1H."""
    try:
        import yfinance as yf
        df = yf.download("^NSEI", period="60d", interval="1h", progress=False)
        if df is None or df.empty:
            log.warning("yfinance returned empty 1H data")
            return
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "dt", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        # Convert to IST (UTC+5:30)
        if df["dt"].dt.tz is not None:
            df["dt"] = df["dt"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        df["dt"] = df["dt"].astype(str)
        archive_save("nifty_1h", df[["dt", "open", "high", "low", "close", "volume"]],
                     dedupe_on="dt")
        log.info(f"Nifty 1H: {len(df)} candles fetched (archive cumulative)")
    except Exception as e:
        log.error(f"fetch_nifty_1h failed: {e}")


# ── Nifty OHLC (for chart + zones) ───────────────────────────────────────────

def fetch_nifty_ohlc():
    """
    NSE API caps at ~70 rows per call (~3 months).
    Fetch two overlapping chunks and merge for ~6 months of data.
    """
    from datetime import date, timedelta
    today = date.today()

    chunks = []
    # Chunk 1: today → ~3 months ago
    to1   = today
    from1 = today - timedelta(days=100)
    df1 = fetch_with_retry(
        capital_market.index_data, index="NIFTY 50",
        from_date=from1.strftime("%d-%m-%Y"),
        to_date=to1.strftime("%d-%m-%Y"),
    )
    if df1 is not None:
        chunks.append(df1)

    time.sleep(1)

    # Chunk 2: ~3 months ago → ~6 months ago
    to2   = from1 - timedelta(days=1)
    from2 = today - timedelta(days=200)
    df2 = fetch_with_retry(
        capital_market.index_data, index="NIFTY 50",
        from_date=from2.strftime("%d-%m-%Y"),
        to_date=to2.strftime("%d-%m-%Y"),
    )
    if df2 is not None:
        chunks.append(df2)

    if chunks:
        combined = pd.concat(chunks, ignore_index=True).drop_duplicates(subset=["TIMESTAMP"])
        archive_save("nifty_ohlc", combined, dedupe_on="TIMESTAMP")
        log.info(f"Nifty OHLC: {len(combined)} rows fetched (archive cumulative)")


# ── F&O Participant OI ────────────────────────────────────────────────────────

def fetch_participant_oi():
    trade_date = today_trade_date()
    df = fetch_with_retry(derivatives.participant_wise_open_interest, trade_date=trade_date)
    if df is not None:
        save("participant_oi", df)


def fetch_fii_derivatives():
    trade_date = today_trade_date()
    df = fetch_with_retry(derivatives.fii_derivatives_statistics, trade_date=trade_date)
    if df is not None:
        save("fii_derivatives", df)


# ── Bulk & Block Deals ────────────────────────────────────────────────────────

def fetch_deals():
    df_bulk = fetch_with_retry(capital_market.bulk_deal_data, period="1W")
    if df_bulk is not None:
        save("bulk_deals", df_bulk)

    df_block = fetch_with_retry(capital_market.block_deals_data, period="1W")
    if df_block is not None:
        save("block_deals", df_block)


# ── High Delivery % Screener ──────────────────────────────────────────────────

def build_nifty500_symbols() -> list[str]:
    """Combine Nifty 50 + Next 50 + Midcap 150 + Smallcap 250 = ~500 symbols."""
    all_symbols = set()
    fetchers = [
        capital_market.nifty50_equity_list,
        capital_market.niftynext50_equity_list,
        capital_market.niftymidcap150_equity_list,
        capital_market.niftysmallcap250_equity_list,
    ]
    for fn in fetchers:
        try:
            df = fn()
            if df is not None and not df.empty:
                sym_col = next((c for c in df.columns if "symbol" in c.lower()), None)
                if sym_col:
                    all_symbols.update(df[sym_col].dropna().tolist())
        except Exception as e:
            log.warning(f"{fn.__name__}: {e}")
    return sorted(all_symbols)


def fetch_high_delivery():
    """
    For Nifty 500, fetch 10-day delivery data and find stocks where
    average delivery % > 60% over the last 10 trading days.
    """
    symbols = build_nifty500_symbols()
    if not symbols:
        log.error("No symbols fetched for Nifty 500")
        return

    log.info(f"Scanning delivery % for {len(symbols)} symbols...")
    dates = last_n_trading_dates(10)
    from_date = dates[-1]  # oldest
    to_date = dates[0]     # newest

    results = []
    for i, sym in enumerate(symbols):
        try:
            df = capital_market.deliverable_position_data(
                symbol=sym, from_date=from_date, to_date=to_date
            )
            if df is None or df.empty:
                continue
            del_col = next(
                (c for c in df.columns if "deliv" in c.lower() and "%" in c), None
            )
            if del_col is None:
                del_col = next(
                    (c for c in df.columns if "deliv" in c.lower() and "perc" in c.lower()), None
                )
            if del_col is None:
                continue
            df[del_col] = pd.to_numeric(df[del_col], errors="coerce")
            avg_del = df[del_col].mean()
            min_del = df[del_col].min()
            if avg_del >= 60 and min_del >= 40:  # avg > 60, never dropped below 40
                results.append({
                    "symbol": sym,
                    "avg_delivery_pct": round(avg_del, 2),
                    "min_delivery_pct": round(min_del, 2),
                    "max_delivery_pct": round(df[del_col].max(), 2),
                    "days_checked": len(df),
                })
        except Exception as e:
            log.debug(f"Delivery {sym}: {e}")
        if (i + 1) % 50 == 0:
            log.info(f"  Delivery scan: {i+1}/{len(symbols)} done")
        time.sleep(0.3)

    if results:
        df_out = pd.DataFrame(results).sort_values("avg_delivery_pct", ascending=False)
        save("high_delivery", df_out)
        log.info(f"High delivery screener: {len(results)} stocks qualify")
    else:
        log.warning("No stocks qualified for high delivery screener")


# ── Intraday Signals ──────────────────────────────────────────────────────────

def fetch_52_week_highs():
    trade_date = today_trade_date()
    df = fetch_with_retry(capital_market.week_52_high_low_report, trade_date=trade_date)
    if df is not None:
        save("week_52_high_low", df)


def fetch_most_active():
    df_val = fetch_with_retry(capital_market.most_active_equities, fetch_by="value")
    if df_val is not None:
        df_val["fetch_by"] = "value"
        save("most_active_value", df_val)

    df_vol = fetch_with_retry(capital_market.most_active_equities, fetch_by="volume")
    if df_vol is not None:
        df_vol["fetch_by"] = "volume"
        save("most_active_volume", df_vol)


def fetch_gainers_losers():
    df_g = fetch_with_retry(capital_market.top_gainers_or_losers, to_get="gainers")
    if df_g is not None:
        save("top_gainers", df_g)

    df_l = fetch_with_retry(capital_market.top_gainers_or_losers, to_get="loosers")
    if df_l is not None:
        save("top_losers", df_l)


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_eod_fetch():
    """7 PM fetch — full EOD data + delivery screener."""
    log.info("=== EOD FETCH STARTED ===")
    start = time.time()

    fetch_vix()
    fetch_advance_decline()
    fetch_nifty_ohlc()
    fetch_nifty_1h()
    fetch_sector_performance()
    fetch_fii_dii()
    fetch_participant_oi()
    fetch_fii_derivatives()
    fetch_deals()
    fetch_52_week_highs()
    fetch_most_active()
    fetch_gainers_losers()
    fetch_high_delivery()  # slowest — runs last

    save_meta("last_eod_fetch", datetime.now().isoformat())
    elapsed = round(time.time() - start, 1)
    log.info(f"=== EOD FETCH COMPLETE in {elapsed}s ===")


def run_morning_fetch():
    """9 AM fetch — fast pre-market data (FII/DII, indices, derivatives)."""
    log.info("=== MORNING FETCH STARTED ===")
    start = time.time()

    fetch_vix()
    fetch_nifty_1h()
    fetch_fii_dii()
    fetch_sector_performance()
    fetch_gainers_losers()
    fetch_most_active()

    save_meta("last_morning_fetch", datetime.now().isoformat())
    elapsed = round(time.time() - start, 1)
    log.info(f"=== MORNING FETCH COMPLETE in {elapsed}s ===")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "eod"
    if mode == "morning":
        run_morning_fetch()
    elif mode == "eod":
        run_eod_fetch()
    elif mode == "quick":
        # Fast test run — skips the slow delivery screener
        fetch_vix()
        fetch_advance_decline()
        fetch_nifty_ohlc()
        fetch_nifty_1h()
        fetch_fii_dii()
        fetch_sector_performance()
        fetch_deals()
        fetch_gainers_losers()
        fetch_most_active()
        fetch_participant_oi()
        fetch_fii_derivatives()
        fetch_52_week_highs()
        save_meta("last_quick_fetch", datetime.now().isoformat())
        log.info("=== QUICK FETCH COMPLETE ===")
    else:
        print("Usage: python3 fetcher.py [eod|morning|quick]")
