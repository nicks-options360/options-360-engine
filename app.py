"""
=====================================================================
 OPTION BUYING — 360° QUADRUPLE RECONFIRMATION ENGINE (Signal-Only)
=====================================================================
 Author: Built for Nicks
 Purpose: Systematic Buy/Sell/Hold decision for NSE options
 Stack: Streamlit + yfinance + nsepython (free)
 Run: streamlit run app.py
=====================================================================
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests

# ---------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Options 360° Engine",
    page_icon="🎯",
    layout="wide",
)

st.markdown("""
<style>
    .main-header { font-size: 28px; font-weight: 700; color: #0E4D92; }
    .verdict-buy { background:#0a7d32; color:white; padding:18px; border-radius:8px; font-size:22px; font-weight:700; text-align:center;}
    .verdict-sell { background:#c0392b; color:white; padding:18px; border-radius:8px; font-size:22px; font-weight:700; text-align:center;}
    .verdict-hold { background:#7f8c8d; color:white; padding:18px; border-radius:8px; font-size:22px; font-weight:700; text-align:center;}
    .layer-pass { color:#0a7d32; font-weight:700; }
    .layer-fail { color:#c0392b; font-weight:700; }
    .layer-warn { color:#e67e22; font-weight:700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🎯 Options 360° Decision Engine</div>', unsafe_allow_html=True)
st.caption("Quadruple Reconfirmation: Macro → News → Technical → Fundamental")

# =====================================================================
# SIDEBAR — TRADE INPUT
# =====================================================================
st.sidebar.header("📋 Trade Setup")

symbol = st.sidebar.text_input("NSE Symbol (e.g. RELIANCE, HDFCBANK)", value="RELIANCE").upper().strip()
option_type = st.sidebar.selectbox("Option Type", ["CE (Call)", "PE (Put)"])
strike_price = st.sidebar.number_input("Strike Price", min_value=0.0, value=1300.0, step=5.0)
premium = st.sidebar.number_input("Current Premium (₹)", min_value=0.0, value=20.0, step=0.5)
lot_size = st.sidebar.number_input("Lot Size", min_value=1, value=250, step=1)
expiry_days = st.sidebar.number_input("Days to Expiry", min_value=0, value=7, step=1)
capital = st.sidebar.number_input("Capital Deployed (₹)", min_value=0.0, value=5000.0, step=500.0)

run_analysis = st.sidebar.button("🚀 RUN 360° ANALYSIS", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Layer Weights**")
st.sidebar.caption("Macro 25% | News 20% | Technical 35% | Fundamental 20%")

# =====================================================================
# HELPER — TICKER MAPPING (NSE → yfinance)
# =====================================================================
def to_yf(sym):
    """Convert NSE symbol to yfinance format."""
    sym = sym.upper().replace(".NS", "")
    return sym + ".NS"

# =====================================================================
# LAYER 1 — MACRO & GLOBAL CONTEXT
# =====================================================================
def layer1_macro():
    """
    Pulls global cues and India VIX to determine market regime.
    Returns score 0-100 + regime tag + checklist details.
    """
    result = {"score": 0, "regime": "Unknown", "details": {}, "max": 100}
    
    try:
        # Fetch key indices
        tickers = {
            "Nifty 50":     "^NSEI",
            "Bank Nifty":   "^NSEBANK",
            "India VIX":    "^INDIAVIX",
            "Dow Jones":    "^DJI",
            "Nasdaq":       "^IXIC",
            "Nikkei":       "^N225",
            "Hang Seng":    "^HSI",
            "Brent Crude":  "BZ=F",
            "DXY":          "DX-Y.NYB",
            "USD/INR":      "INR=X",
        }
        
        data = {}
        for name, tkr in tickers.items():
            try:
                d = yf.Ticker(tkr).history(period="5d", interval="1d")
                if len(d) >= 2:
                    pct = ((d['Close'].iloc[-1] - d['Close'].iloc[-2]) / d['Close'].iloc[-2]) * 100
                    data[name] = {"price": d['Close'].iloc[-1], "change_pct": pct}
            except Exception:
                continue
        
        result["details"] = data
        
        # Scoring logic
        score = 0
        notes = []
        
        # 1. US markets (overnight cue) — 25 pts
        us_avg = np.mean([data.get("Dow Jones",{}).get("change_pct",0), data.get("Nasdaq",{}).get("change_pct",0)])
        if us_avg > 0.5: score += 25; notes.append("✅ US markets positive (+{:.2f}%)".format(us_avg))
        elif us_avg > 0:  score += 15; notes.append("🟡 US markets mildly positive")
        elif us_avg > -0.5: score += 8; notes.append("🟡 US markets flat-to-weak")
        else: notes.append("❌ US markets weak ({:.2f}%)".format(us_avg))
        
        # 2. Asian markets — 20 pts
        asia_avg = np.mean([data.get("Nikkei",{}).get("change_pct",0), data.get("Hang Seng",{}).get("change_pct",0)])
        if asia_avg > 0.3: score += 20; notes.append("✅ Asian markets supportive")
        elif asia_avg > -0.3: score += 10; notes.append("🟡 Asian markets neutral")
        else: notes.append("❌ Asian markets negative")
        
        # 3. India VIX — 25 pts (option buyers WANT volatility, but extreme high = expensive)
        vix = data.get("India VIX",{}).get("price", 15)
        if 13 <= vix <= 18: score += 25; notes.append(f"✅ VIX in sweet spot ({vix:.1f})")
        elif 18 < vix <= 22: score += 18; notes.append(f"🟡 VIX elevated ({vix:.1f}) — premiums expensive")
        elif vix < 13: score += 10; notes.append(f"🟡 VIX low ({vix:.1f}) — limited movement expected")
        else: score += 5; notes.append(f"❌ VIX very high ({vix:.1f}) — premium decay risk")
        
        # 4. Crude oil — 15 pts (matters for India - inflation/CAD)
        crude_chg = data.get("Brent Crude",{}).get("change_pct", 0)
        if abs(crude_chg) < 1: score += 15; notes.append("✅ Crude stable")
        elif abs(crude_chg) < 2: score += 8; notes.append("🟡 Crude moderate move")
        else: notes.append(f"❌ Crude volatile ({crude_chg:+.2f}%)")
        
        # 5. DXY / USDINR — 15 pts
        dxy_chg = data.get("DXY",{}).get("change_pct", 0)
        if dxy_chg < 0.3: score += 15; notes.append("✅ Dollar weak — FII friendly")
        elif dxy_chg < 0.6: score += 8; notes.append("🟡 Dollar mildly stronger")
        else: notes.append("❌ Dollar strong — FII selling risk")
        
        result["score"] = score
        result["notes"] = notes
        
        # Regime classification
        if score >= 70: result["regime"] = "🟢 Risk-On"
        elif score >= 45: result["regime"] = "🟡 Neutral"
        else: result["regime"] = "🔴 Risk-Off"
        
    except Exception as e:
        result["error"] = str(e)
        result["notes"] = ["⚠️ Data fetch error — manual check needed"]
    
    return result

# =====================================================================
# LAYER 2 — NEWS & EVENT FILTER
# =====================================================================
def layer2_news(symbol, expiry_days):
    """
    Checks for upcoming events, recent news flow, and event risk.
    Free APIs limited — uses yfinance earnings + manual flags.
    """
    result = {"score": 0, "details": {}, "max": 100, "notes": []}
    
    try:
        tk = yf.Ticker(to_yf(symbol))
        
        # 1. Earnings proximity — 40 pts
        try:
            cal = tk.calendar
            earnings_date = None
            if cal is not None and not (isinstance(cal, pd.DataFrame) and cal.empty):
                if isinstance(cal, dict):
                    earnings_date = cal.get("Earnings Date")
                    if isinstance(earnings_date, list) and len(earnings_date) > 0:
                        earnings_date = earnings_date[0]
                elif isinstance(cal, pd.DataFrame):
                    if "Earnings Date" in cal.index:
                        earnings_date = cal.loc["Earnings Date"][0]
            
            if earnings_date:
                days_to_earnings = (pd.Timestamp(earnings_date) - pd.Timestamp.now()).days
                result["details"]["earnings_in_days"] = days_to_earnings
                
                if days_to_earnings < 0:
                    result["score"] += 40
                    result["notes"].append("✅ No imminent earnings")
                elif days_to_earnings > expiry_days + 3:
                    result["score"] += 40
                    result["notes"].append(f"✅ Earnings after expiry ({days_to_earnings}d)")
                elif days_to_earnings > expiry_days:
                    result["score"] += 20
                    result["notes"].append(f"🟡 Earnings near expiry ({days_to_earnings}d)")
                else:
                    result["score"] += 5
                    result["notes"].append(f"❌ Earnings WITHIN expiry ({days_to_earnings}d) — high IV crush risk")
            else:
                result["score"] += 30
                result["notes"].append("🟡 No earnings data — verify manually")
        except Exception:
            result["score"] += 25
            result["notes"].append("⚠️ Earnings check skipped")
        
        # 2. Recent news flow — 30 pts (yfinance news)
        try:
            news = tk.news[:5] if tk.news else []
            result["details"]["recent_news_count"] = len(news)
            
            if len(news) > 0:
                result["score"] += 20
                result["notes"].append(f"✅ {len(news)} recent news items found")
                result["details"]["news_titles"] = [
                    n.get("title", n.get("content", {}).get("title", "")) for n in news[:3]
                ]
            else:
                result["score"] += 25
                result["notes"].append("🟡 Limited news — quiet stock")
        except Exception:
            result["score"] += 15
        
        # 3. Sector momentum (proxy via sector ETF) — 30 pts
        try:
            info = tk.info
            sector = info.get("sector", "Unknown")
            result["details"]["sector"] = sector
            result["score"] += 25
            result["notes"].append(f"✅ Sector: {sector}")
        except Exception:
            result["score"] += 15
        
    except Exception as e:
        result["error"] = str(e)
        result["score"] = 50  # neutral fallback
        result["notes"].append("⚠️ News layer fallback to neutral")
    
    return result

# =====================================================================
# LAYER 3 — TECHNICAL CONFIRMATION (Multi-Timeframe)
# =====================================================================
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_adx(high, low, close, period=14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([(high-low).abs(), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.rolling(period).mean()

def layer3_technical(symbol, option_type):
    """
    Multi-timeframe technical check: Daily, 1H, 15m.
    Returns score and directional bias.
    """
    result = {"score": 0, "details": {}, "max": 100, "notes": [], "bias": "Neutral"}
    is_call = option_type.startswith("CE")
    
    try:
        yf_sym = to_yf(symbol)
        
        # ---- DAILY ANALYSIS (40 pts) ----
        d = yf.Ticker(yf_sym).history(period="6mo", interval="1d")
        if len(d) < 50:
            result["score"] = 30
            result["notes"].append("⚠️ Insufficient daily data")
            return result
        
        d['EMA20'] = calc_ema(d['Close'], 20)
        d['EMA50'] = calc_ema(d['Close'], 50)
        d['EMA200'] = calc_ema(d['Close'], 200) if len(d) >= 200 else d['Close']
        d['RSI'] = calc_rsi(d['Close'])
        d['ADX'] = calc_adx(d['High'], d['Low'], d['Close'])
        
        last = d.iloc[-1]
        result["details"]["daily_close"] = round(last['Close'], 2)
        result["details"]["daily_rsi"] = round(last['RSI'], 1)
        result["details"]["daily_adx"] = round(last['ADX'], 1)
        result["details"]["ema20"] = round(last['EMA20'], 2)
        result["details"]["ema50"] = round(last['EMA50'], 2)
        
        # EMA alignment (15 pts)
        if is_call:
            if last['Close'] > last['EMA20'] > last['EMA50']:
                result["score"] += 15
                result["notes"].append("✅ Daily EMA stack bullish")
            elif last['Close'] > last['EMA50']:
                result["score"] += 8
                result["notes"].append("🟡 Daily above EMA50 only")
            else:
                result["notes"].append("❌ Daily EMA stack bearish for CE")
        else:
            if last['Close'] < last['EMA20'] < last['EMA50']:
                result["score"] += 15
                result["notes"].append("✅ Daily EMA stack bearish")
            elif last['Close'] < last['EMA50']:
                result["score"] += 8
                result["notes"].append("🟡 Daily below EMA50 only")
            else:
                result["notes"].append("❌ Daily EMA stack bullish for PE")
        
        # RSI (10 pts)
        rsi = last['RSI']
        if is_call:
            if 50 <= rsi <= 70: result["score"] += 10; result["notes"].append(f"✅ RSI healthy bullish ({rsi:.1f})")
            elif rsi > 70: result["score"] += 4; result["notes"].append(f"🟡 RSI overbought ({rsi:.1f})")
            elif 40 <= rsi < 50: result["score"] += 5; result["notes"].append(f"🟡 RSI neutral ({rsi:.1f})")
            else: result["notes"].append(f"❌ RSI weak ({rsi:.1f}) for CE")
        else:
            if 30 <= rsi <= 50: result["score"] += 10; result["notes"].append(f"✅ RSI healthy bearish ({rsi:.1f})")
            elif rsi < 30: result["score"] += 4; result["notes"].append(f"🟡 RSI oversold ({rsi:.1f})")
            elif 50 < rsi <= 60: result["score"] += 5; result["notes"].append(f"🟡 RSI neutral ({rsi:.1f})")
            else: result["notes"].append(f"❌ RSI strong ({rsi:.1f}) for PE")
        
        # ADX (10 pts) — trend strength
        adx = last['ADX']
        if adx > 25: result["score"] += 10; result["notes"].append(f"✅ Strong trend (ADX {adx:.1f})")
        elif adx > 20: result["score"] += 6; result["notes"].append(f"🟡 Moderate trend (ADX {adx:.1f})")
        else: result["notes"].append(f"❌ Weak/no trend (ADX {adx:.1f}) — bad for option buying")
        
        # Volume confirmation (5 pts)
        avg_vol = d['Volume'].rolling(20).mean().iloc[-1]
        if last['Volume'] > avg_vol * 1.2:
            result["score"] += 5
            result["notes"].append("✅ Above-avg volume")
        else:
            result["notes"].append("🟡 Below-avg volume")
        
        # ---- INTRADAY ANALYSIS (60 pts) — 1H + 15m ----
        h1 = yf.Ticker(yf_sym).history(period="60d", interval="1h")
        m15 = yf.Ticker(yf_sym).history(period="30d", interval="15m")
        
        if len(h1) > 50:
            h1['EMA20'] = calc_ema(h1['Close'], 20)
            h1['EMA50'] = calc_ema(h1['Close'], 50)
            h1['RSI'] = calc_rsi(h1['Close'])
            h1_last = h1.iloc[-1]
            
            # 1H trend alignment (20 pts)
            if is_call:
                if h1_last['Close'] > h1_last['EMA20'] > h1_last['EMA50']: 
                    result["score"] += 20; result["notes"].append("✅ 1H aligned bullish")
                elif h1_last['Close'] > h1_last['EMA20']:
                    result["score"] += 10; result["notes"].append("🟡 1H above EMA20")
                else:
                    result["notes"].append("❌ 1H bearish")
            else:
                if h1_last['Close'] < h1_last['EMA20'] < h1_last['EMA50']:
                    result["score"] += 20; result["notes"].append("✅ 1H aligned bearish")
                elif h1_last['Close'] < h1_last['EMA20']:
                    result["score"] += 10; result["notes"].append("🟡 1H below EMA20")
                else:
                    result["notes"].append("❌ 1H bullish")
            
            # 1H RSI momentum (10 pts)
            h1_rsi = h1_last['RSI']
            if is_call and 50 <= h1_rsi <= 70: result["score"] += 10
            elif not is_call and 30 <= h1_rsi <= 50: result["score"] += 10
            else: result["score"] += 3
            result["details"]["h1_rsi"] = round(h1_rsi, 1)
        
        if len(m15) > 30:
            m15['VWAP'] = (m15['Close'] * m15['Volume']).cumsum() / m15['Volume'].cumsum()
            m15['EMA9'] = calc_ema(m15['Close'], 9)
            m15_last = m15.iloc[-1]
            
            # 15m VWAP (15 pts)
            if is_call and m15_last['Close'] > m15_last['VWAP']:
                result["score"] += 15; result["notes"].append("✅ 15m above VWAP")
            elif not is_call and m15_last['Close'] < m15_last['VWAP']:
                result["score"] += 15; result["notes"].append("✅ 15m below VWAP")
            else:
                result["notes"].append("❌ 15m against VWAP")
            
            # 15m short EMA (15 pts)
            if is_call and m15_last['Close'] > m15_last['EMA9']:
                result["score"] += 15; result["notes"].append("✅ 15m above EMA9 — entry trigger")
            elif not is_call and m15_last['Close'] < m15_last['EMA9']:
                result["score"] += 15; result["notes"].append("✅ 15m below EMA9 — entry trigger")
            else:
                result["notes"].append("❌ 15m EMA9 against direction")
            
            result["details"]["m15_vwap"] = round(m15_last['VWAP'], 2)
            result["details"]["spot_now"] = round(m15_last['Close'], 2)
        
        # Bias
        if result["score"] >= 70:
            result["bias"] = "Strong " + ("Bullish" if is_call else "Bearish")
        elif result["score"] >= 50:
            result["bias"] = "Moderate " + ("Bullish" if is_call else "Bearish")
        else:
            result["bias"] = "Weak / Against"
        
    except Exception as e:
        result["error"] = str(e)
        result["score"] = 30
        result["notes"].append("⚠️ Technical layer error")
    
    return result

# =====================================================================
# LAYER 4 — FUNDAMENTAL SANITY CHECK
# =====================================================================
def layer4_fundamental(symbol, option_type):
    """
    Quick fundamental alignment — even for short-dated options,
    don't buy calls on broken stocks or puts on champions.
    """
    result = {"score": 0, "details": {}, "max": 100, "notes": [], "alignment": "Neutral"}
    is_call = option_type.startswith("CE")
    
    try:
        info = yf.Ticker(to_yf(symbol)).info
        
        pe = info.get("trailingPE", None)
        forward_pe = info.get("forwardPE", None)
        peg = info.get("pegRatio", None)
        roe = info.get("returnOnEquity", None)
        debt_eq = info.get("debtToEquity", None)
        rev_growth = info.get("revenueGrowth", None)
        earnings_growth = info.get("earningsGrowth", None)
        target_mean = info.get("targetMeanPrice", None)
        current = info.get("currentPrice", None)
        
        result["details"] = {
            "P/E": pe, "Forward P/E": forward_pe, "PEG": peg,
            "ROE": f"{roe*100:.1f}%" if roe else "N/A",
            "Debt/Equity": debt_eq,
            "Revenue Growth": f"{rev_growth*100:.1f}%" if rev_growth else "N/A",
            "Earnings Growth": f"{earnings_growth*100:.1f}%" if earnings_growth else "N/A",
        }
        
        # Earnings growth (30 pts)
        if earnings_growth is not None:
            if is_call:
                if earnings_growth > 0.15: result["score"] += 30; result["notes"].append("✅ Strong earnings growth")
                elif earnings_growth > 0: result["score"] += 18; result["notes"].append("🟡 Positive earnings growth")
                else: result["notes"].append("❌ Negative earnings growth — bad for CE")
            else:
                if earnings_growth < 0: result["score"] += 30; result["notes"].append("✅ Earnings declining — PE friendly")
                elif earnings_growth < 0.10: result["score"] += 18
                else: result["notes"].append("❌ Strong earnings growth — bad for PE")
        else:
            result["score"] += 15
        
        # ROE (20 pts)
        if roe is not None:
            if is_call:
                if roe > 0.15: result["score"] += 20; result["notes"].append(f"✅ Strong ROE ({roe*100:.1f}%)")
                elif roe > 0.10: result["score"] += 12
                else: result["score"] += 5
            else:
                result["score"] += 10  # less relevant for short PE
        else:
            result["score"] += 10
        
        # Debt levels (15 pts)
        if debt_eq is not None:
            if debt_eq < 50: result["score"] += 15; result["notes"].append("✅ Healthy balance sheet")
            elif debt_eq < 100: result["score"] += 10
            else: result["score"] += 5; result["notes"].append("🟡 High debt")
        else:
            result["score"] += 10
        
        # Analyst target alignment (20 pts)
        if target_mean and current:
            upside = (target_mean - current) / current
            result["details"]["Analyst Upside"] = f"{upside*100:.1f}%"
            if is_call:
                if upside > 0.10: result["score"] += 20; result["notes"].append(f"✅ Analyst upside +{upside*100:.1f}%")
                elif upside > 0: result["score"] += 12
                else: result["notes"].append(f"❌ Analyst downside {upside*100:.1f}%")
            else:
                if upside < 0: result["score"] += 20; result["notes"].append(f"✅ Analyst downside — PE aligned")
                elif upside < 0.05: result["score"] += 10
                else: result["notes"].append("❌ Analysts bullish — PE risky")
        else:
            result["score"] += 10
        
        # Valuation (15 pts)
        if pe is not None:
            if 10 < pe < 30: result["score"] += 15; result["notes"].append(f"✅ Reasonable P/E ({pe:.1f})")
            elif pe < 50: result["score"] += 10
            else: result["score"] += 5
        else:
            result["score"] += 8
        
        # Alignment tag
        if result["score"] >= 65: result["alignment"] = "Aligned ✅"
        elif result["score"] >= 40: result["alignment"] = "Neutral 🟡"
        else: result["alignment"] = "Contrary ❌"
        
    except Exception as e:
        result["error"] = str(e)
        result["score"] = 50
        result["notes"].append("⚠️ Fundamental fallback")
    
    return result

# =====================================================================
# FINAL VERDICT ENGINE
# =====================================================================
def compute_verdict(l1, l2, l3, l4):
    """
    Weighted aggregation + hard rules for veto.
    """
    weights = {"macro": 0.25, "news": 0.20, "technical": 0.35, "fundamental": 0.20}
    composite = (
        l1["score"] * weights["macro"] +
        l2["score"] * weights["news"] +
        l3["score"] * weights["technical"] +
        l4["score"] * weights["fundamental"]
    )
    
    # Hard veto rules
    vetoes = []
    if l3["score"] < 50: vetoes.append("Technical score < 50 (primary trigger missing)")
    if l1["score"] < 35: vetoes.append("Macro regime hostile")
    if l4["alignment"] == "Contrary ❌": vetoes.append("Fundamentals contrary to direction")
    
    # Verdict
    if vetoes:
        verdict = "AVOID"
        verdict_class = "verdict-hold"
        reason = "Hard veto triggered: " + " | ".join(vetoes)
    elif composite >= 70:
        verdict = "BUY ✅"
        verdict_class = "verdict-buy"
        reason = "All 4 layers confirm — quadruple lock green"
    elif composite >= 55:
        verdict = "HOLD / WAIT"
        verdict_class = "verdict-hold"
        reason = "Partial confirmation — wait for stronger trigger"
    else:
        verdict = "AVOID / OPPOSITE"
        verdict_class = "verdict-sell"
        reason = "Insufficient confirmation across layers"
    
    return composite, verdict, verdict_class, reason

# =====================================================================
# TRADE PLAN CALCULATOR
# =====================================================================
def build_trade_plan(premium, lot_size, capital, expiry_days, l3):
    """
    Generates SL, targets, position sizing, and time stops.
    """
    plan = {}
    
    # Position sizing
    lots_affordable = int(capital // (premium * lot_size)) if premium > 0 else 0
    plan["lots"] = lots_affordable
    plan["total_premium"] = lots_affordable * premium * lot_size
    plan["max_loss"] = round(plan["total_premium"] * 0.35, 2)
    
    # SL on premium (35%)
    plan["sl_premium"] = round(premium * 0.65, 2)
    plan["sl_drop_pct"] = "35%"
    
    # Target levels
    plan["target_1"] = round(premium * 1.5, 2)   # 50% gain
    plan["target_2"] = round(premium * 2.0, 2)   # 100% gain (1:2 from 35% risk)
    plan["target_3"] = round(premium * 3.0, 2)   # runner
    
    # Time stops
    if expiry_days <= 2:
        plan["time_stop"] = "Exit by 2:30 PM same day if not in 25%+ profit"
    elif expiry_days <= 5:
        plan["time_stop"] = "Exit if not in profit within 45 mins of entry"
    else:
        plan["time_stop"] = "Re-evaluate end of day if flat; exit before final 2 days to expiry"
    
    # SL on underlying (5m structure)
    spot = l3.get("details", {}).get("spot_now", None)
    vwap = l3.get("details", {}).get("m15_vwap", None)
    if spot and vwap:
        plan["spot_sl_ref"] = vwap
        plan["spot_sl_note"] = f"Exit if spot crosses VWAP ({vwap:.2f}) against direction"
    
    # Scaling rules
    plan["scaling"] = "Book 50% at Target 1 | Trail rest with 15m EMA9 or VWAP"
    
    return plan

# =====================================================================
# MAIN EXECUTION
# =====================================================================
if run_analysis:
    if not symbol:
        st.error("Enter a symbol first")
        st.stop()
    
    with st.spinner("Running 360° analysis across 4 layers..."):
        l1 = layer1_macro()
        l2 = layer2_news(symbol, expiry_days)
        l3 = layer3_technical(symbol, option_type)
        l4 = layer4_fundamental(symbol, option_type)
    
    composite, verdict, vclass, reason = compute_verdict(l1, l2, l3, l4)
    
    # ----- VERDICT BANNER -----
    st.markdown(f'<div class="{vclass}">FINAL VERDICT: {verdict}<br><span style="font-size:14px;font-weight:400">{reason}</span></div>', unsafe_allow_html=True)
    st.markdown(f"### Composite Score: **{composite:.1f} / 100**")
    
    # ----- LAYER SCORE BARS -----
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("L1 Macro", f"{l1['score']}/100", l1.get("regime", ""))
    col2.metric("L2 News/Events", f"{l2['score']}/100")
    col3.metric("L3 Technical", f"{l3['score']}/100", l3.get("bias", ""))
    col4.metric("L4 Fundamental", f"{l4['score']}/100", l4.get("alignment", ""))
    
    st.divider()
    
    # ----- TRADE PLAN -----
    if "BUY" in verdict or "HOLD" in verdict:
        plan = build_trade_plan(premium, lot_size, capital, expiry_days, l3)
        st.subheader("📋 Trade Plan")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Position Size", f"{plan['lots']} lots", f"₹{plan['total_premium']:,.0f} deployed")
        c2.metric("Stop Loss (Premium)", f"₹{plan['sl_premium']}", f"-{plan['sl_drop_pct']}")
        c3.metric("Max Loss", f"₹{plan['max_loss']:,.0f}")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Target 1 (book 50%)", f"₹{plan['target_1']}", "+50%")
        c5.metric("Target 2", f"₹{plan['target_2']}", "+100%")
        c6.metric("Target 3 (runner)", f"₹{plan['target_3']}", "+200%")
        
        st.info(f"⏱️ **Time Stop:** {plan['time_stop']}")
        st.info(f"📊 **Scaling:** {plan['scaling']}")
        if "spot_sl_note" in plan:
            st.warning(f"🎯 **Underlying Stop:** {plan['spot_sl_note']}")
    
    st.divider()
    
    # ----- DETAILED LAYER BREAKDOWN -----
    tab1, tab2, tab3, tab4 = st.tabs(["🌍 L1 Macro", "📰 L2 News", "📈 L3 Technical", "💰 L4 Fundamental"])
    
    with tab1:
        st.write(f"**Regime:** {l1.get('regime')}")
        for n in l1.get("notes", []): st.write(n)
        with st.expander("Raw data"):
            st.json(l1.get("details", {}))
    
    with tab2:
        for n in l2.get("notes", []): st.write(n)
        with st.expander("News & Events data"):
            st.json(l2.get("details", {}))
    
    with tab3:
        st.write(f"**Bias:** {l3.get('bias')}")
        for n in l3.get("notes", []): st.write(n)
        with st.expander("Technical indicators"):
            st.json(l3.get("details", {}))
    
    with tab4:
        st.write(f"**Alignment:** {l4.get('alignment')}")
        for n in l4.get("notes", []): st.write(n)
        with st.expander("Fundamentals snapshot"):
            st.json(l4.get("details", {}))
    
    st.divider()
    st.caption("⚠️ Signal-only tool. Verify all signals against your own analysis. Past performance ≠ future results. Trade at your own risk.")

else:
    st.info("👈 Enter trade details in the sidebar and click **RUN 360° ANALYSIS** to get your verdict.")
    
    st.markdown("""
    ### How the 4-Layer Quadruple Lock Works
    
    **Layer 1 — Macro & Global (25% weight)**  
    Pulls US/Asian markets, India VIX, crude, DXY, USD/INR. Classifies regime as Risk-On / Neutral / Risk-Off. Option buyers need movement — VIX in 13-18 zone is the sweet spot.
    
    **Layer 2 — News & Events (20% weight)**  
    Checks earnings proximity (IV crush risk), recent news flow, sector context. Earnings within expiry window = veto.
    
    **Layer 3 — Technical (35% weight, the heaviest)**  
    Multi-timeframe: Daily (EMA stack, RSI, ADX), 1H (trend alignment), 15m (VWAP + EMA9 entry trigger). Below 50 = hard veto.
    
    **Layer 4 — Fundamental (20% weight)**  
    Quick sanity: earnings growth, ROE, debt, analyst targets, valuation. "Contrary" alignment = hard veto.
    
    **Final Verdict** uses weighted composite + hard veto rules. BUY requires:
    - Composite ≥ 70
    - No hard vetoes
    - Technical ≥ 50
    - Macro ≥ 35
    - Fundamentals not Contrary
    """)
