# NSE Trading Dashboard

A public, auto-refreshing intraday & positional dashboard for **NIFTY 50** — built with Streamlit, Plotly, and the [nselib](https://pypi.org/project/nselib/) Python package.

## What it shows

- **Market mood banner** — composite score combining VIX, A/D ratio, FII/DII flows, sector breadth
- **Nifty 50 chart** — daily zones + 1H intraday entry signals (3 detector types: Zone-Touch, PDH/PDL, Gap-Fade)
- **Backtest** — configurable wick-based SL, R:R, BE trigger, trail-to-swing-low (sliders)
- **Sector rotation** — performance heatmap, leaders/laggards
- **FII/DII activity** — cash and derivatives breakdown
- **F&O participant OI** — directional index futures + net call/put buying sentiment
- **Bulk/block deals**, 52-week highs, top gainers/losers, most active
- **Positional watch** — high-delivery screener (10-day avg ≥ 60%)

## Auto-refresh

GitHub Actions runs the fetcher **twice daily** (IST):

- **9:05 AM** (morning) — VIX, FII/DII, sectors, 1H bars, gainers/losers
- **7:05 PM** (EOD) — full data + delivery screener + complete 1H candles for the day

CSVs are committed to the repo. Streamlit Cloud auto-redeploys on each push.

## Run locally

```bash
git clone https://github.com/<your-username>/nse-dashboard.git
cd nse-dashboard
pip install -r requirements.txt
python fetcher.py quick    # one-time data pull (~2-4 min)
streamlit run app.py
```

Open http://localhost:8501

## Deploy your own

1. Fork this repo on GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app" → connect your fork
3. Enable GitHub Actions: Settings → Actions → "Allow all actions"
4. The morning/EOD workflows run automatically once Actions is enabled

## Architecture

```
GitHub Actions (cron) ──► fetcher.py ──► CSVs in data/ ──► git commit/push
                                                            │
                                                            ▼
                                                Streamlit Cloud (auto-redeploys)
                                                            │
                                                            ▼
                                                  Public dashboard URL
```

## Disclaimer

This dashboard is for **educational and informational purposes only**. It is **not** investment advice. The author is not a SEBI-registered investment advisor. Trading involves substantial risk of loss. Past performance does not predict future results. Always consult a qualified financial advisor before making investment decisions.

## Tech stack

- **Streamlit** — UI framework
- **Plotly** — interactive candlestick & charts (with auto-rescale Y on zoom via injected JS)
- **nselib** — NSE India public-API wrapper
- **yfinance** — 1H Nifty intraday data (60-day rolling window, archived cumulatively)
- **pandas / numpy** — data manipulation
- **GitHub Actions** — scheduled data fetcher

## License

MIT — see LICENSE file.
