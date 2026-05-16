# Options 360° Decision Engine

A signal-only Streamlit app that applies a **4-layer quadruple reconfirmation** framework before suggesting Buy / Hold / Avoid on NSE options.

## What it does

For any NSE option you enter (symbol, strike, premium, expiry, capital), it runs 4 parallel checks:

| Layer | Weight | Checks |
|---|---|---|
| **L1 Macro** | 25% | US/Asia markets, India VIX, Brent, DXY, USD/INR — classifies regime |
| **L2 News/Events** | 20% | Earnings proximity, news flow, sector context |
| **L3 Technical** | 35% | Daily + 1H + 15m: EMA stack, RSI, ADX, VWAP, EMA9 trigger |
| **L4 Fundamental** | 20% | Earnings growth, ROE, debt, analyst targets, P/E |

Each layer scores 0-100. A composite score plus hard-veto rules produces the final verdict and a complete trade plan (position size, premium SL, 3 targets, time stop, underlying stop).

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Run
streamlit run app.py
```

App opens at `http://localhost:8501`.

## Verdict Logic

**BUY** requires ALL of:
- Composite ≥ 70
- Technical ≥ 50 (no veto)
- Macro ≥ 35 (no veto)
- Fundamental not "Contrary" (no veto)

**HOLD/WAIT** = composite 55-70, no vetoes
**AVOID** = anything else or any veto fired

## Trade Plan Outputs

- **Position size**: how many lots your capital affords
- **SL premium**: 35% drop from entry (hard stop)
- **Targets**: 50% / 100% / 200% of premium (3-tier exit)
- **Time stop**: scaled by days-to-expiry
- **Underlying SL**: VWAP-based reference
- **Scaling rule**: book 50% at T1, trail rest on 15m EMA9/VWAP

## Limitations (and Phase 2 upgrades)

Free APIs have gaps. The next iteration should add:

1. **NSE option chain** — real IV percentile, OI buildup, PCR, max pain (use `nsepython` library)
2. **News sentiment** — Economic Times RSS, Moneycontrol scraping with sentiment scoring
3. **FII/DII data** — daily cash + F&O participation (NSE BhavCopy)
4. **Sector breadth** — advance/decline of sector constituents
5. **Greeks** — delta/theta/gamma per strike (use `mibian` or `py_vollib`)
6. **Backtesting module** — replay historical setups to validate scoring weights

## Architecture Notes

The app is structured so each layer is an independent function returning a dict with `{score, details, notes}`. To swap data sources or add layers:

- Replace yfinance calls in `layer1_macro()` with broker API (Kite/Upstox)
- Add `layer5_orderflow()` for OI/PCR/max-pain from NSE chain
- Modify weights in `compute_verdict()` to retune

## Disclaimer

Signal-only. No order placement. Verify every signal against your own judgment and the live order book. Markets change faster than any single tool can capture.
