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
st.caption("5-Layer Reconfirmation: Macro → News → Technical → Fundamental → Option Chain")

# Initialize session state for auto-filled values
# Initialize session state — use widget keys directly (the Streamlit-recommended pattern)
# This avoids the value=/key= conflict that prevents programmatic updates.
if "strike_widget" not in st.session_state:
    st.session_state.strike_widget = 1300.0
if "premium_widget" not in st.session_state:
    st.session_state.premium_widget = 20.0
if "lot_widget" not in st.session_state:
    st.session_state.lot_widget = 250
if "dte_widget" not in st.session_state:
    st.session_state.dte_widget = 7
if "capital_widget" not in st.session_state:
    st.session_state.capital_widget = 5000.0
if "chain_data" not in st.session_state:
    st.session_state.chain_data = None
if "chain_symbol" not in st.session_state:
    st.session_state.chain_symbol = ""

# Pending auto-fill values — set by buttons, applied at next script start
if "pending_fill" not in st.session_state:
    st.session_state.pending_fill = None

# Apply any pending auto-fill BEFORE widgets are instantiated
# This is the bulletproof Streamlit pattern for programmatic widget updates
if st.session_state.pending_fill is not None:
    fill = st.session_state.pending_fill
    if "strike" in fill:
        st.session_state.strike_widget = float(fill["strike"])
    if "premium" in fill:
        st.session_state.premium_widget = float(fill["premium"])
    if "lot" in fill:
        st.session_state.lot_widget = int(fill["lot"])
    if "dte" in fill:
        st.session_state.dte_widget = int(fill["dte"])
    st.session_state.last_fill_message = fill.get("message", "")
    st.session_state.pending_fill = None  # consume it

# NSE F&O Lot Sizes — sourced from user-uploaded NSE CSV (May-26 cycle).
# 213 contracts including major stocks + indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY).
# IMPORTANT: 46 stocks have lot size CHANGES from Jun-26 → Jul-26 cycle. Examples below.
# Always verify current cycle's lot size against your broker terminal before trading.
#
# Notable upcoming changes (Jun-26 → Jul-26):
#   HDFCBANK: 550 → 650 | ITC: 1600 → 1725 | TCS: 175 → 200 | RELIANCE: 500 → 550
#   AMBUJACEM: 1050 → 1200 | CIPLA: 375 → 425 | HCLTECH: 350 → 400 | GAIL: 3150 → 3550
#   COFORGE: 375 → 475 | DLF: 825 → 950 | IRFC: 4250 → 5425 | INOXWIND: 3575 → 6400
NSE_LOT_SIZES = {
    "360ONE": 500, "ABB": 125, "ABCAPITAL": 3100, "ADANIENSOL": 675, "ADANIENT": 309,
    "ADANIGREEN": 600, "ADANIPORTS": 475, "ADANIPOWER": 3550, "ALKEM": 125, "AMBER": 100,
    "AMBUJACEM": 1050, "ANGELONE": 2500, "APLAPOLLO": 350, "APOLLOHOSP": 125, "ASHOKLEY": 5000,
    "ASIANPAINT": 250, "ASTRAL": 425, "AUBANK": 1000, "AUROPHARMA": 550, "AXISBANK": 625,
    "BAJAJ-AUTO": 75, "BAJAJFINSV": 250, "BAJAJHLDNG": 50, "BAJFINANCE": 750, "BANDHANBNK": 3600,
    "BANKBARODA": 2925, "BANKINDIA": 5200, "BANKNIFTY": 30, "BDL": 350, "BEL": 1425,
    "BHARATFORG": 500, "BHARTIARTL": 475, "BHEL": 2625, "BIOCON": 2500, "BLUESTARCO": 325,
    "BOSCHLTD": 25, "BPCL": 1975, "BRITANNIA": 125, "BSE": 375, "CAMS": 750,
    "CANBK": 6750, "CDSL": 475, "CGPOWER": 850, "CHOLAFIN": 625, "CIPLA": 375,
    "COALINDIA": 1350, "COCHINSHIP": 400, "COFORGE": 375, "COLPAL": 225, "CONCOR": 1250,
    "CROMPTON": 1800, "CUMMINSIND": 200, "DABUR": 1250, "DALBHARAT": 325, "DELHIVERY": 2075,
    "DIVISLAB": 100, "DIXON": 50, "DLF": 825, "DMART": 150, "DRREDDY": 625,
    "EICHERMOT": 100, "ETERNAL": 2425, "EXIDEIND": 1800, "FEDERALBNK": 2500, "FINNIFTY": 60,
    "FORCEMOT": 25, "FORTIS": 775, "GAIL": 3150, "GLENMARK": 375, "GMRAIRPORT": 6975,
    "GODFRYPHLP": 275, "GODREJCP": 500, "GODREJPROP": 275, "GRASIM": 250, "HAL": 150,
    "HAVELLS": 500, "HCLTECH": 350, "HDFCAMC": 300, "HDFCBANK": 550, "HDFCLIFE": 1100,
    "HEROMOTOCO": 150, "HINDALCO": 700, "HINDPETRO": 2025, "HINDUNILVR": 300, "HINDZINC": 1225,
    "HYUNDAI": 275, "ICICIBANK": 700, "ICICIGI": 325, "ICICIPRULI": 925, "IDEA": 71475,
    "IDFCFIRSTB": 9275, "IEX": 3750, "INDHOTEL": 1000, "INDIANB": 1000, "INDIGO": 150,
    "INDUSINDBK": 700, "INDUSTOWER": 1700, "INFY": 400, "INOXWIND": 3575, "IOC": 4875,
    "IREDA": 3450, "IRFC": 4250, "ITC": 1600, "JINDALSTEL": 625, "JIOFIN": 2350,
    "JSWENERGY": 1000, "JSWSTEEL": 675, "JUBLFOOD": 1250, "KALYANKJIL": 1175, "KAYNES": 100,
    "KEI": 175, "KFINTECH": 500, "KOTAKBANK": 2000, "KPITTECH": 425, "LAURUSLABS": 850,
    "LICHSGFIN": 1000, "LICI": 700, "LODHA": 450, "LT": 175, "LTF": 2250,
    "LTM": 150, "LUPIN": 425, "MANAPPURAM": 3000, "MANKIND": 225, "MARICO": 1200,
    "MARUTI": 50, "MAXHEALTH": 525, "MAZDOCK": 200, "MCX": 625, "MFSL": 400,
    "MIDCPNIFTY": 120, "M&M": 200, "MOTHERSON": 6150, "MOTILALOFS": 775, "MPHASIS": 275,
    "MUTHOOTFIN": 275, "NAM-INDIA": 625, "NATIONALUM": 1875, "NAUKRI": 375, "NBCC": 6500,
    "NESTLEIND": 500, "NHPC": 6400, "NIFTY": 65, "NMDC": 6750, "NTPC": 1500,
    "NUVAMA": 500, "NYKAA": 3125, "OBEROIRLTY": 350, "OFSS": 75, "OIL": 1400,
    "ONGC": 2250, "PAGEIND": 15, "PATANJALI": 900, "PAYTM": 725, "PERSISTENT": 100,
    "PETRONET": 1900, "PFC": 1300, "PGEL": 950, "PHOENIXLTD": 350, "PIDILITIND": 500,
    "PIIND": 175, "PNB": 8000, "PNBHOUSING": 650, "POLICYBZR": 350, "POLYCAB": 125,
    "POWERGRID": 1900, "POWERINDIA": 25, "PREMIERENE": 575, "PRESTIGE": 450, "RBLBANK": 3175,
    "RECLTD": 1400, "RELIANCE": 500, "RVNL": 1525, "SAIL": 4700, "SAMMAANCAP": 4300,
    "SBICARD": 800, "SBILIFE": 375, "SBIN": 750, "SHREECEM": 25, "SHRIRAMFIN": 825,
    "SIEMENS": 175, "SOLARINDS": 50, "SONACOMS": 1225, "SRF": 200, "SUNPHARMA": 350,
    "SUPREMEIND": 175, "SUZLON": 9025, "SWIGGY": 1300, "TATACONSUM": 550, "TATAELXSI": 100,
    "TATAPOWER": 1450, "TATASTEEL": 2750, "TCS": 175, "TECHM": 600, "TIINDIA": 200,
    "TITAN": 175, "TMPV": 800, "TORNTPHARM": 125, "TRENT": 100, "TVSMOTOR": 175,
    "ULTRACEMCO": 50, "UNIONBANK": 4425, "UNITDSPR": 400, "UNOMINDA": 550, "UPL": 1355,
    "VBL": 1125, "VEDL": 1150, "VMM": 4850, "VOLTAS": 375, "WAAREEENER": 175,
    "WIPRO": 3000, "YESBANK": 31100, "ZYDUSLIFE": 900,
}

def get_lot_size(symbol):
    """Get NSE F&O lot size for a symbol. Returns default 100 if unknown.
    Source: NSE CSV (May-26 cycle). NSE revises lot sizes quarterly.
    Always cross-verify with your broker terminal before trading."""
    return NSE_LOT_SIZES.get(symbol.upper().replace(".NS", ""), 100)

# =====================================================================
# SIDEBAR — TRADE INPUT
# =====================================================================
st.sidebar.header("📋 Trade Setup")

# Show auto-fill confirmation banner in sidebar (clears after viewing)
if st.session_state.get("last_fill_message"):
    st.sidebar.success(st.session_state.last_fill_message)
    st.session_state.last_fill_message = ""  # consume so it doesn't persist

symbol = st.sidebar.text_input("NSE Symbol (e.g. RELIANCE, HDFCBANK)", value="RELIANCE").upper().strip()
option_type = st.sidebar.selectbox("Option Type", ["CE (Call)", "PE (Put)"])

fetch_chain = st.sidebar.button("📊 Try Fetching Option Chain", use_container_width=True, help="NSE may block cloud IPs. If it fails, just enter Strike + Premium manually below from your broker terminal.")

strike_price = st.sidebar.number_input(
    "Strike Price",
    min_value=0.0,
    step=5.0,
    key="strike_widget",
    help="Enter strike from your broker terminal, or use Auto-Fill after fetching chain.",
)
premium = st.sidebar.number_input(
    "Current Premium (₹)",
    min_value=0.0,
    step=0.5,
    key="premium_widget",
    help="Enter live premium from your broker terminal. Will be cleared to 0 after Auto-Fill in fallback mode.",
)
lot_size = st.sidebar.number_input(
    "Lot Size",
    min_value=1,
    step=1,
    key="lot_widget",
    help="Auto-filled from NSE F&O list (May-26 cycle). Verify with broker.",
)
expiry_days = st.sidebar.number_input(
    "Days to Expiry",
    min_value=0,
    step=1,
    key="dte_widget",
)
capital = st.sidebar.number_input(
    "Capital Deployed (₹)",
    min_value=0.0,
    step=500.0,
    key="capital_widget",
)

run_analysis = st.sidebar.button("🚀 RUN 360° ANALYSIS", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Layer Weights**")
st.sidebar.caption("Macro 20% | News 15% | Technical 30% | Fundamental 15% | Option Chain 20%")

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
# OPTION CHAIN FETCHER (NSEPython with robust fallbacks)
# =====================================================================
def fetch_option_chain(symbol):
    """
    Fetches NSE option chain. Returns dict with:
    - spot, expiries, chain (DataFrame), error (if any), diagnostics
    Has fallbacks: tries nsepython → direct NSE → returns helpful error with HTTP details
    """
    result = {"success": False, "spot": None, "expiries": [], "chain": None, "error": None, "diagnostics": []}
    
    # ---- Check market hours (helps diagnose weekend issues) ----
    from datetime import datetime
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    hour = now.hour
    is_market_hours = (9 <= hour <= 15) and not is_weekend
    if is_weekend:
        result["diagnostics"].append("⚠️ Today is a weekend (NSE closed) — option chain API often unreliable")
    elif not is_market_hours:
        result["diagnostics"].append(f"⚠️ Outside market hours (now {hour}:xx IST) — NSE data may be stale")
    
    # ---- Method 1: nsepython ----
    try:
        from nsepython import nse_optionchain_scrapper
        data = nse_optionchain_scrapper(symbol)
        if data and "records" in data:
            spot = data["records"].get("underlyingValue")
            expiries = data["records"].get("expiryDates", [])
            raw = data["records"].get("data", [])
            
            if not raw:
                result["diagnostics"].append("nsepython returned empty 'data' array — possibly weekend/holiday")
            
            rows = []
            for item in raw:
                strike = item.get("strikePrice")
                expiry = item.get("expiryDate")
                ce = item.get("CE", {}) or {}
                pe = item.get("PE", {}) or {}
                rows.append({
                    "strike": strike,
                    "expiry": expiry,
                    "ce_ltp": ce.get("lastPrice", 0),
                    "ce_oi": ce.get("openInterest", 0),
                    "ce_oi_chg": ce.get("changeinOpenInterest", 0),
                    "ce_volume": ce.get("totalTradedVolume", 0),
                    "ce_iv": ce.get("impliedVolatility", 0),
                    "ce_bid": ce.get("bidprice", 0),
                    "ce_ask": ce.get("askPrice", 0),
                    "pe_ltp": pe.get("lastPrice", 0),
                    "pe_oi": pe.get("openInterest", 0),
                    "pe_oi_chg": pe.get("changeinOpenInterest", 0),
                    "pe_volume": pe.get("totalTradedVolume", 0),
                    "pe_iv": pe.get("impliedVolatility", 0),
                    "pe_bid": pe.get("bidprice", 0),
                    "pe_ask": pe.get("askPrice", 0),
                })
            
            df = pd.DataFrame(rows)
            if not df.empty:
                result.update({
                    "success": True,
                    "spot": spot,
                    "expiries": expiries,
                    "chain": df,
                })
                result["diagnostics"].append(f"✅ nsepython succeeded ({len(df)} strikes)")
                return result
            else:
                result["diagnostics"].append("nsepython parsed but resulted in empty DataFrame")
        else:
            result["diagnostics"].append(f"nsepython returned unexpected structure: {type(data).__name__}")
    except Exception as e:
        result["diagnostics"].append(f"nsepython exception: {type(e).__name__}: {str(e)[:150]}")
    
    # ---- Method 2: Direct NSE API (fallback) with HTTP status diagnostics ----
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
            "Connection": "keep-alive",
        }
        session = requests.Session()
        session.headers.update(headers)
        
        # Cookie warmup
        try:
            r0 = session.get("https://www.nseindia.com", timeout=10)
            result["diagnostics"].append(f"NSE homepage HTTP {r0.status_code}")
        except Exception as e:
            result["diagnostics"].append(f"NSE homepage unreachable: {type(e).__name__}")
        
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        r = session.get(url, timeout=15)
        result["diagnostics"].append(f"NSE option-chain API HTTP {r.status_code}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                spot = data.get("records", {}).get("underlyingValue")
                raw = data.get("records", {}).get("data", [])
                if not raw:
                    result["diagnostics"].append("API returned 200 but empty data — likely market closed or symbol invalid")
                rows = []
                for item in raw:
                    strike = item.get("strikePrice")
                    expiry = item.get("expiryDate")
                    ce = item.get("CE", {}) or {}
                    pe = item.get("PE", {}) or {}
                    rows.append({
                        "strike": strike, "expiry": expiry,
                        "ce_ltp": ce.get("lastPrice", 0), "ce_oi": ce.get("openInterest", 0),
                        "ce_oi_chg": ce.get("changeinOpenInterest", 0),
                        "ce_volume": ce.get("totalTradedVolume", 0),
                        "ce_iv": ce.get("impliedVolatility", 0),
                        "pe_ltp": pe.get("lastPrice", 0), "pe_oi": pe.get("openInterest", 0),
                        "pe_oi_chg": pe.get("changeinOpenInterest", 0),
                        "pe_volume": pe.get("totalTradedVolume", 0),
                        "pe_iv": pe.get("impliedVolatility", 0),
                    })
                df = pd.DataFrame(rows)
                if not df.empty:
                    result.update({"success": True, "spot": spot, "chain": df})
                    result["diagnostics"].append(f"✅ Direct API succeeded ({len(df)} strikes)")
                    return result
            except ValueError as e:
                result["diagnostics"].append(f"API returned 200 but invalid JSON: {str(e)[:100]}")
        elif r.status_code == 401:
            result["diagnostics"].append("HTTP 401 — NSE requires authentication (session cookie failed)")
        elif r.status_code == 403:
            result["diagnostics"].append("HTTP 403 — NSE is actively BLOCKING this IP (cloud server detected)")
        elif r.status_code == 429:
            result["diagnostics"].append("HTTP 429 — rate limited. Wait 60s and retry.")
        elif r.status_code in (502, 503, 504):
            result["diagnostics"].append(f"HTTP {r.status_code} — NSE server unavailable. Try in 5 min.")
    except requests.exceptions.Timeout:
        result["diagnostics"].append("Request timeout — slow network or NSE not responding")
    except Exception as e:
        result["diagnostics"].append(f"Direct API exception: {type(e).__name__}: {str(e)[:150]}")
    
    # ---- Method 3: yfinance-based degraded fallback ----
    # Gives spot + historical volatility (HV as IV proxy). No live OI/PCR.
    try:
        yf_sym = symbol + ".NS" if not symbol.endswith(".NS") else symbol
        tk = yf.Ticker(yf_sym)
        info = tk.info
        spot_yf = info.get("currentPrice") or info.get("regularMarketPrice")
        
        if spot_yf:
            hist = tk.history(period="3mo", interval="1d")
            if len(hist) > 20:
                returns = hist["Close"].pct_change().dropna()
                hist_vol = float(returns.std() * (252 ** 0.5) * 100)
                
                result["diagnostics"].append(f"⚙️ yfinance fallback engaged. Spot ₹{spot_yf:.2f}, HV {hist_vol:.1f}%")
                result["success"] = True
                result["spot"] = spot_yf
                result["fallback_mode"] = True
                result["hist_vol"] = hist_vol
                result["chain"] = pd.DataFrame([])
                return result
    except Exception as e:
        result["diagnostics"].append(f"yfinance fallback exception: {type(e).__name__}: {str(e)[:120]}")
    
    # ---- Compose honest error message ----
    if is_weekend:
        result["error"] = "Markets closed (weekend). NSE option chain API typically doesn't serve data on Saturdays/Sundays. Try Monday 9:30 AM IST."
    elif not is_market_hours:
        result["error"] = "Outside market hours. NSE option chain data is most reliable during 9:15 AM - 3:30 PM IST on weekdays."
    else:
        # Check diagnostics to give honest reason
        diag_text = " ".join(result["diagnostics"])
        if "403" in diag_text:
            result["error"] = "NSE is blocking cloud server IPs (HTTP 403). This is a known issue with cloud-hosted apps. Solutions: 1) Try again in 30s. 2) Run app locally on your PC. 3) Use Kite Connect API."
        elif "429" in diag_text:
            result["error"] = "Rate limited by NSE (HTTP 429). Too many recent requests. Wait 60 seconds."
        elif "401" in diag_text:
            result["error"] = "NSE auth handshake failed. Cookie session not established. Retry in 30s."
        elif "timeout" in diag_text.lower():
            result["error"] = "Network timeout — NSE servers slow or unreachable. Retry in a moment."
        elif "empty" in diag_text.lower():
            result["error"] = "NSE responded but returned no data. Possible reasons: invalid symbol, no F&O contracts, or market data not updated yet."
        else:
            result["error"] = "Unknown failure. See diagnostics tab for HTTP details."
    
    return result


def filter_chain_for_expiry(chain_df, expiry_str=None):
    """Filter option chain to nearest weekly expiry (or specified)."""
    if chain_df is None or chain_df.empty:
        return chain_df
    if expiry_str:
        return chain_df[chain_df["expiry"] == expiry_str].copy()
    # Auto: pick the nearest expiry
    try:
        chain_df["expiry_dt"] = pd.to_datetime(chain_df["expiry"], format="%d-%b-%Y", errors="coerce")
        nearest = chain_df["expiry_dt"].min()
        return chain_df[chain_df["expiry_dt"] == nearest].copy()
    except Exception:
        return chain_df


# =====================================================================
# LAYER 5 — OPTION CHAIN HEALTH
# =====================================================================
def layer5_option_chain(chain_data, symbol, strike_price, option_type, premium=None, expiry_days=7):
    """
    The institutional edge layer.
    Checks: PCR, Max Pain, IV vs chain, OI buildup at strike, ATM IV percentile.
    Fallback mode: uses yfinance spot + HV for theoretical premium check.
    """
    result = {"score": 0, "details": {}, "max": 100, "notes": [], "health": "Unknown"}
    is_call = option_type.startswith("CE")
    
    if not chain_data or not chain_data.get("success"):
        # No chain available — score neutral and explain
        result["score"] = 50
        result["notes"].append("⚠️ Option chain not available — scored neutral. Click 'Fetch Live Option Chain' in sidebar.")
        result["health"] = "Data Unavailable 🟡"
        result["details"]["error"] = chain_data.get("error") if chain_data else "Not fetched"
        return result
    
    # ---- FALLBACK MODE: yfinance-based partial signals ----
    if chain_data.get("fallback_mode"):
        spot = chain_data["spot"]
        hist_vol = chain_data.get("hist_vol", 25)
        result["details"]["spot"] = round(spot, 2)
        result["details"]["historical_vol"] = f"{hist_vol:.1f}%"
        result["details"]["data_source"] = "yfinance (NSE chain blocked)"
        
        # 1. Moneyness check (25 pts)
        moneyness_pct = ((strike_price - spot) / spot) * 100
        result["details"]["moneyness_pct"] = f"{moneyness_pct:+.2f}%"
        if is_call:
            if -2 <= moneyness_pct <= 2: result["score"] += 25; result["notes"].append(f"✅ Near-ATM strike ({moneyness_pct:+.1f}%) — good liquidity zone")
            elif 2 < moneyness_pct <= 5: result["score"] += 15; result["notes"].append(f"🟡 Mildly OTM ({moneyness_pct:+.1f}%)")
            elif moneyness_pct > 5: result["score"] += 5; result["notes"].append(f"❌ Deep OTM ({moneyness_pct:+.1f}%) — lottery ticket risk")
            else: result["score"] += 18; result["notes"].append(f"🟡 ITM ({moneyness_pct:+.1f}%) — pays for intrinsic")
        else:
            if -2 <= moneyness_pct <= 2: result["score"] += 25; result["notes"].append(f"✅ Near-ATM strike ({moneyness_pct:+.1f}%) — good liquidity zone")
            elif -5 <= moneyness_pct < -2: result["score"] += 15; result["notes"].append(f"🟡 Mildly OTM ({moneyness_pct:+.1f}%)")
            elif moneyness_pct < -5: result["score"] += 5; result["notes"].append(f"❌ Deep OTM ({moneyness_pct:+.1f}%) — lottery ticket risk")
            else: result["score"] += 18; result["notes"].append(f"🟡 ITM ({moneyness_pct:+.1f}%) — pays for intrinsic")
        
        # 2. Theoretical premium check using simplified Black-Scholes (35 pts)
        if premium and premium > 0:
            try:
                import math
                T = max(expiry_days / 365.0, 1/365)  # avoid div by zero
                sigma = hist_vol / 100.0
                r = 0.07  # India risk-free rate ~7%
                S = spot
                K = strike_price
                
                # Simplified theoretical option price (Black-Scholes)
                d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
                d2 = d1 - sigma*math.sqrt(T)
                
                # Normal CDF approximation
                def norm_cdf(x):
                    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
                
                if is_call:
                    theo_price = S*norm_cdf(d1) - K*math.exp(-r*T)*norm_cdf(d2)
                else:
                    theo_price = K*math.exp(-r*T)*norm_cdf(-d2) - S*norm_cdf(-d1)
                
                theo_price = max(theo_price, 0.5)  # floor at 0.5
                result["details"]["theoretical_premium"] = round(theo_price, 2)
                result["details"]["actual_premium"] = premium
                
                premium_ratio = premium / theo_price
                result["details"]["premium_vs_theoretical"] = f"{premium_ratio:.2f}x"
                
                if 0.85 <= premium_ratio <= 1.15: result["score"] += 35; result["notes"].append(f"✅ Premium fair (₹{premium} vs theoretical ₹{theo_price:.2f})")
                elif 0.7 <= premium_ratio < 0.85: result["score"] += 28; result["notes"].append(f"✅ Premium cheap ({premium_ratio:.2f}x theo)")
                elif 1.15 < premium_ratio <= 1.4: result["score"] += 15; result["notes"].append(f"🟡 Premium expensive ({premium_ratio:.2f}x theo) — overpaying ~{(premium_ratio-1)*100:.0f}%")
                elif premium_ratio > 1.4: result["score"] += 5; result["notes"].append(f"❌ Premium very expensive ({premium_ratio:.2f}x theo) — high IV, overpaying")
                else: result["score"] += 20; result["notes"].append(f"🟡 Premium suspiciously cheap — verify quote")
            except Exception as e:
                result["score"] += 17
                result["notes"].append(f"🟡 Theoretical price calc skipped: {str(e)[:80]}")
        else:
            result["score"] += 17
        
        # 3. Volatility regime (25 pts)
        if 18 <= hist_vol <= 30: result["score"] += 25; result["notes"].append(f"✅ Healthy HV ({hist_vol:.1f}%) — good for buying")
        elif 30 < hist_vol <= 45: result["score"] += 15; result["notes"].append(f"🟡 Elevated HV ({hist_vol:.1f}%) — premiums expensive")
        elif hist_vol < 18: result["score"] += 10; result["notes"].append(f"🟡 Low HV ({hist_vol:.1f}%) — limited movement expected")
        else: result["score"] += 5; result["notes"].append(f"❌ Very high HV ({hist_vol:.1f}%) — IV crush risk")
        
        # 4. Time-to-expiry sanity (15 pts)
        if expiry_days >= 5: result["score"] += 15; result["notes"].append(f"✅ Reasonable time ({expiry_days}d) — theta manageable")
        elif expiry_days >= 2: result["score"] += 8; result["notes"].append(f"🟡 Short DTE ({expiry_days}d) — aggressive theta")
        else: result["score"] += 3; result["notes"].append(f"❌ Very short DTE ({expiry_days}d) — high gamma+theta risk")
        
        result["notes"].append("ℹ️ Limited mode — no PCR/MaxPain/OI signals (NSE chain blocked)")
        
        if result["score"] >= 70: result["health"] = "Strong (HV-based) ✅"
        elif result["score"] >= 50: result["health"] = "Moderate (HV-based) 🟡"
        else: result["health"] = "Weak (HV-based) ❌"
        
        return result
    
    # ---- FULL MODE: NSE option chain available ----
    try:
        chain = chain_data["chain"]
        spot = chain_data["spot"]
        
        # Filter to nearest expiry
        df = filter_chain_for_expiry(chain)
        if df is None or df.empty:
            result["score"] = 50
            result["notes"].append("⚠️ No expiry data parsed")
            return result
        
        # ---- 1. Put-Call Ratio (PCR) — 20 pts ----
        total_pe_oi = df["pe_oi"].sum()
        total_ce_oi = df["ce_oi"].sum()
        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
        result["details"]["PCR"] = round(pcr, 2)
        
        if is_call:
            if pcr > 1.3: result["score"] += 20; result["notes"].append(f"✅ PCR {pcr:.2f} — contrarian bullish (puts oversold)")
            elif pcr > 1.0: result["score"] += 14; result["notes"].append(f"🟡 PCR {pcr:.2f} — mildly bullish")
            elif pcr > 0.7: result["score"] += 8; result["notes"].append(f"🟡 PCR {pcr:.2f} — neutral")
            else: result["notes"].append(f"❌ PCR {pcr:.2f} — calls overcrowded, bearish for CE")
        else:
            if pcr < 0.7: result["score"] += 20; result["notes"].append(f"✅ PCR {pcr:.2f} — contrarian bearish (calls oversold)")
            elif pcr < 1.0: result["score"] += 14; result["notes"].append(f"🟡 PCR {pcr:.2f} — mildly bearish")
            elif pcr < 1.3: result["score"] += 8; result["notes"].append(f"🟡 PCR {pcr:.2f} — neutral")
            else: result["notes"].append(f"❌ PCR {pcr:.2f} — puts overcrowded, bearish for PE")
        
        # ---- 2. Max Pain — 20 pts ----
        # Max pain = strike where total OI value is minimized for writers
        strikes = df["strike"].unique()
        pain = {}
        for s in strikes:
            ce_pain = ((df["strike"] - s).clip(lower=0) * df["ce_oi"]).sum()
            pe_pain = ((s - df["strike"]).clip(lower=0) * df["pe_oi"]).sum()
            pain[s] = ce_pain + pe_pain
        if pain:
            max_pain_strike = min(pain, key=pain.get)
            result["details"]["max_pain"] = max_pain_strike
            result["details"]["spot_vs_maxpain"] = f"Spot {spot:.0f} vs MaxPain {max_pain_strike}"
            
            mp_diff_pct = (spot - max_pain_strike) / max_pain_strike * 100
            
            if is_call:
                if mp_diff_pct < -1: result["score"] += 20; result["notes"].append(f"✅ Spot below MaxPain ({mp_diff_pct:+.1f}%) — magnet UP for CE")
                elif mp_diff_pct < 0.5: result["score"] += 12; result["notes"].append(f"🟡 Spot near MaxPain — balanced")
                else: result["notes"].append(f"❌ Spot above MaxPain ({mp_diff_pct:+.1f}%) — pressure DOWN against CE")
            else:
                if mp_diff_pct > 1: result["score"] += 20; result["notes"].append(f"✅ Spot above MaxPain ({mp_diff_pct:+.1f}%) — magnet DOWN for PE")
                elif mp_diff_pct > -0.5: result["score"] += 12; result["notes"].append(f"🟡 Spot near MaxPain — balanced")
                else: result["notes"].append(f"❌ Spot below MaxPain ({mp_diff_pct:+.1f}%) — pressure UP against PE")
        
        # ---- 3. OI Buildup at Strike — 25 pts ----
        # Find the row matching user's strike (or nearest)
        df["strike_dist"] = (df["strike"] - strike_price).abs()
        row = df.nsmallest(1, "strike_dist").iloc[0]
        
        if is_call:
            ce_oi_chg = row["ce_oi_chg"]
            ce_ltp = row["ce_ltp"]
            result["details"]["ce_oi"] = int(row["ce_oi"])
            result["details"]["ce_oi_change"] = int(ce_oi_chg)
            # Long Buildup: price up + OI up (we infer price up from spot vs prev close — proxy: positive OI chg + healthy LTP)
            if ce_oi_chg > 0 and ce_ltp > 0:
                # Compare buildup intensity vs total OI
                buildup_pct = (ce_oi_chg / max(row["ce_oi"], 1)) * 100
                if buildup_pct > 15: result["score"] += 25; result["notes"].append(f"✅ Strong CE buildup at strike (+{buildup_pct:.0f}%)")
                elif buildup_pct > 5: result["score"] += 15; result["notes"].append(f"🟡 Moderate CE buildup (+{buildup_pct:.0f}%)")
                else: result["score"] += 8; result["notes"].append(f"🟡 Mild CE buildup")
            elif ce_oi_chg < 0:
                result["notes"].append("🟡 CE OI unwinding at strike — caution")
                result["score"] += 5
        else:
            pe_oi_chg = row["pe_oi_chg"]
            pe_ltp = row["pe_ltp"]
            result["details"]["pe_oi"] = int(row["pe_oi"])
            result["details"]["pe_oi_change"] = int(pe_oi_chg)
            if pe_oi_chg > 0 and pe_ltp > 0:
                buildup_pct = (pe_oi_chg / max(row["pe_oi"], 1)) * 100
                if buildup_pct > 15: result["score"] += 25; result["notes"].append(f"✅ Strong PE buildup at strike (+{buildup_pct:.0f}%)")
                elif buildup_pct > 5: result["score"] += 15; result["notes"].append(f"🟡 Moderate PE buildup (+{buildup_pct:.0f}%)")
                else: result["score"] += 8; result["notes"].append(f"🟡 Mild PE buildup")
            elif pe_oi_chg < 0:
                result["notes"].append("🟡 PE OI unwinding at strike — caution")
                result["score"] += 5
        
        # ---- 4. IV Reasonableness — 20 pts ----
        # Compare strike IV vs ATM IV. If strike IV much higher = overpriced.
        df["atm_dist"] = (df["strike"] - spot).abs()
        atm_row = df.nsmallest(1, "atm_dist").iloc[0]
        atm_iv = atm_row["ce_iv"] if is_call else atm_row["pe_iv"]
        strike_iv = row["ce_iv"] if is_call else row["pe_iv"]
        result["details"]["atm_iv"] = round(atm_iv, 1) if atm_iv else 0
        result["details"]["strike_iv"] = round(strike_iv, 1) if strike_iv else 0
        
        if atm_iv > 0 and strike_iv > 0:
            iv_ratio = strike_iv / atm_iv
            if iv_ratio < 1.1: result["score"] += 20; result["notes"].append(f"✅ IV fair (strike {strike_iv:.0f} vs ATM {atm_iv:.0f})")
            elif iv_ratio < 1.3: result["score"] += 12; result["notes"].append(f"🟡 IV slight premium ({iv_ratio:.2f}x ATM)")
            else: result["notes"].append(f"❌ IV expensive ({iv_ratio:.2f}x ATM) — overpaying")
        else:
            result["score"] += 10
            result["notes"].append("🟡 IV data missing — assumed neutral")
        
        # ---- 5. Liquidity at strike — 15 pts ----
        volume = row["ce_volume"] if is_call else row["pe_volume"]
        oi = row["ce_oi"] if is_call else row["pe_oi"]
        result["details"]["strike_volume"] = int(volume)
        result["details"]["strike_oi"] = int(oi)
        
        if volume > 1000 and oi > 5000: result["score"] += 15; result["notes"].append(f"✅ Strong liquidity (Vol {int(volume):,}, OI {int(oi):,})")
        elif volume > 200: result["score"] += 9; result["notes"].append(f"🟡 Moderate liquidity")
        else: result["notes"].append(f"❌ Thin liquidity (Vol {int(volume)}) — slippage risk")
        
        # Health tag
        if result["score"] >= 70: result["health"] = "Strong ✅"
        elif result["score"] >= 50: result["health"] = "Moderate 🟡"
        else: result["health"] = "Weak ❌"
        
    except Exception as e:
        result["error"] = str(e)
        result["score"] = 50
        result["notes"].append(f"⚠️ Option chain layer error: {str(e)[:100]}")
    
    return result


# =====================================================================
# FINAL VERDICT ENGINE
# =====================================================================
def compute_verdict(l1, l2, l3, l4, l5):
    """
    Weighted aggregation + hard rules for veto.
    L5 (Option Chain) is the institutional signal.
    """
    weights = {"macro": 0.20, "news": 0.15, "technical": 0.30, "fundamental": 0.15, "option_chain": 0.20}
    composite = (
        l1["score"] * weights["macro"] +
        l2["score"] * weights["news"] +
        l3["score"] * weights["technical"] +
        l4["score"] * weights["fundamental"] +
        l5["score"] * weights["option_chain"]
    )
    
    # Hard veto rules
    vetoes = []
    if l3["score"] < 50: vetoes.append("Technical score < 50 (primary trigger missing)")
    if l1["score"] < 35: vetoes.append("Macro regime hostile")
    if l4["alignment"] == "Contrary ❌": vetoes.append("Fundamentals contrary to direction")
    if l5["score"] < 35 and l5.get("health") != "Data Unavailable 🟡":
        vetoes.append("Option chain unhealthy (PCR/IV/OI flagged)")
    
    # Verdict
    if vetoes:
        verdict = "AVOID"
        verdict_class = "verdict-hold"
        reason = "Hard veto triggered: " + " | ".join(vetoes)
    elif composite >= 70:
        verdict = "BUY ✅"
        verdict_class = "verdict-buy"
        reason = "All 5 layers confirm — quintuple lock green"
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

# ----- FETCH OPTION CHAIN (separate from analysis run) -----
if fetch_chain:
    if not symbol:
        st.error("Enter a symbol first")
        st.stop()
    with st.spinner(f"📊 Fetching live option chain for {symbol} from NSE..."):
        chain_data = fetch_option_chain(symbol)
        st.session_state.chain_data = chain_data
        st.session_state.chain_symbol = symbol
    
    if chain_data["success"]:
        # Check if it's fallback mode (no actual chain data)
        if chain_data.get("fallback_mode"):
            st.warning(f"⚙️ NSE chain unavailable — using yfinance fallback for {symbol}. Spot: ₹{chain_data['spot']:.2f}, HV: {chain_data.get('hist_vol', 0):.1f}%")
            st.info("ℹ️ Limited mode: L5 will score based on moneyness, theoretical premium (Black-Scholes), and historical volatility instead of PCR/MaxPain/OI. Still useful — just less precise than NSE chain.")
            
            spot_fb = chain_data['spot']
            suggested_lot_fb = get_lot_size(symbol)
            # ATM strike rounded to nearest 5 or 50
            round_to = 50 if spot_fb > 1000 else 5
            suggested_strike_fb = round(spot_fb / round_to) * round_to
            
            st.markdown("### 💡 Suggested Setup (Fallback Mode)")
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Spot", f"₹{spot_fb:.2f}")
            f2.metric("Suggested ATM Strike", f"₹{suggested_strike_fb:.0f}")
            f3.metric("Lot Size (NSE)", f"{suggested_lot_fb}")
            f4.metric("HV (IV proxy)", f"{chain_data.get('hist_vol', 0):.1f}%")
            
            st.markdown("⚠️ **Premium must be entered manually** (no live chain data). Check your broker terminal for current premium at this strike.")
            
            col_btn1, col_btn2 = st.columns([3, 1])
            col_btn1.caption("Auto-fill populates Strike + Lot Size. Premium is cleared to 0 — enter it manually from your broker terminal before running analysis.")
            if col_btn2.button("⚡ Auto-Fill (Partial)", use_container_width=True, type="primary", key="partial_autofill_btn"):
                # Stage the fill — will be applied at the top of next script run
                st.session_state.pending_fill = {
                    "strike": float(suggested_strike_fb),
                    "lot": int(suggested_lot_fb),
                    "premium": 0.0,
                    "message": f"✅ Strike set to ₹{suggested_strike_fb:.0f}, Lot Size set to {suggested_lot_fb}. Premium cleared — enter manually before running analysis.",
                }
                st.rerun()
            
            with st.expander("🔍 Why didn't NSE chain work?"):
                for d in chain_data.get("diagnostics", []):
                    st.write(f"• {d}")
            
            st.stop()
        
        st.success(f"✅ Option chain fetched for {symbol}. Spot: ₹{chain_data['spot']:.2f}")
        df_filtered = filter_chain_for_expiry(chain_data["chain"])
        spot = chain_data["spot"]
        
        st.subheader(f"📊 {symbol} Option Chain — Nearest Expiry")
        st.caption("Click a row's Strike value, then manually update Strike + Premium in sidebar")
        
        # Show ATM ± 8 strikes for readability
        df_filtered["atm_dist"] = (df_filtered["strike"] - spot).abs()
        df_display = df_filtered.nsmallest(17, "atm_dist").sort_values("strike").copy()
        
        # Prepare clean display
        display_cols = {
            "strike": "Strike",
            "ce_ltp": "CE LTP",
            "ce_oi": "CE OI",
            "ce_oi_chg": "CE OI Chg",
            "ce_iv": "CE IV",
            "ce_volume": "CE Vol",
            "pe_volume": "PE Vol",
            "pe_iv": "PE IV",
            "pe_oi_chg": "PE OI Chg",
            "pe_oi": "PE OI",
            "pe_ltp": "PE LTP",
        }
        df_show = df_display[list(display_cols.keys())].rename(columns=display_cols)
        
        # Highlight ATM
        def highlight_atm(row):
            if abs(row["Strike"] - spot) < 0.01 * spot:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)
        
        st.dataframe(df_show.style.apply(highlight_atm, axis=1).format({
            "Strike": "{:.0f}", "CE LTP": "₹{:.2f}", "CE OI": "{:,.0f}", "CE OI Chg": "{:+,.0f}",
            "CE IV": "{:.1f}%", "CE Vol": "{:,.0f}", "PE LTP": "₹{:.2f}", "PE OI": "{:,.0f}",
            "PE OI Chg": "{:+,.0f}", "PE IV": "{:.1f}%", "PE Vol": "{:,.0f}",
        }), use_container_width=True, height=520)
        
        # Quick auto-fill: pick ATM strike + matching premium + lot size + DTE
        atm_row = df_display.iloc[df_display["atm_dist"].argmin()]
        suggested_strike = float(atm_row["strike"])
        suggested_premium = float(atm_row["ce_ltp"] if option_type.startswith("CE") else atm_row["pe_ltp"])
        suggested_lot = get_lot_size(symbol)
        
        # Compute DTE from nearest expiry in the chain
        suggested_dte = 7  # default fallback
        try:
            expiry_str = atm_row.get("expiry")
            if expiry_str:
                from datetime import datetime
                exp_dt = pd.to_datetime(expiry_str, format="%d-%b-%Y", errors="coerce")
                if pd.notna(exp_dt):
                    today = pd.Timestamp.now().normalize()
                    suggested_dte = max((exp_dt - today).days, 0)
        except Exception:
            pass
        
        # Show all 4 suggestions
        st.markdown("### 💡 Suggested Trade Setup (ATM)")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Strike", f"₹{suggested_strike:.0f}")
        s2.metric("Premium", f"₹{suggested_premium:.2f}")
        s3.metric("Lot Size", f"{suggested_lot}")
        s4.metric("Days to Expiry", f"{suggested_dte}d")
        
        # Affordability calc — how many lots fits current capital?
        if suggested_premium > 0:
            lots_affordable = int(capital // (suggested_premium * suggested_lot))
            total_cost = lots_affordable * suggested_premium * suggested_lot
            max_loss_35 = total_cost * 0.35
            
            st.markdown("### 💰 Position Sizing (based on current capital)")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Capital (sidebar)", f"₹{capital:,.0f}")
            p2.metric("Lots Affordable", f"{lots_affordable}", f"₹{total_cost:,.0f} deployed")
            p3.metric("Max Loss (35% SL)", f"₹{max_loss_35:,.0f}")
            p4.metric("Cost per Lot", f"₹{suggested_premium * suggested_lot:,.0f}")
            
            if lots_affordable == 0:
                st.warning(f"⚠️ Current capital ₹{capital:,.0f} is too small for 1 lot (₹{suggested_premium * suggested_lot:,.0f} per lot). Increase capital or pick a cheaper strike.")
        
        # Auto-fill button (fills all 4)
        st.markdown("---")
        col_btn1, col_btn2 = st.columns([3, 1])
        col_btn1.caption("Click **Auto-Fill** to populate Strike, Premium, Lot Size, and DTE in the sidebar.")
        if col_btn2.button("⚡ Auto-Fill ALL", use_container_width=True, type="primary", key="full_autofill_btn"):
            # Stage the fill — will be applied at the top of next script run
            st.session_state.pending_fill = {
                "strike": float(suggested_strike),
                "premium": float(suggested_premium),
                "lot": int(suggested_lot),
                "dte": int(suggested_dte),
                "message": f"✅ All fields auto-filled: Strike ₹{suggested_strike:.0f}, Premium ₹{suggested_premium:.2f}, Lot {suggested_lot}, DTE {suggested_dte}d",
            }
            st.rerun()
        
        st.caption("After auto-fill, click '🚀 RUN 360° ANALYSIS' in the sidebar.")
    else:
        st.error(f"❌ Could not fetch option chain. {chain_data.get('error', '')}")
        st.info("You can still enter strike/premium manually and run analysis — the other 4 layers work fine.")
        
        # Honest diagnostics
        with st.expander("🔍 What actually went wrong? (Diagnostic details)"):
            st.markdown("**Step-by-step what the app tried:**")
            for d in chain_data.get("diagnostics", []):
                st.write(f"• {d}")
            st.markdown("---")
            st.markdown("""
            **How to interpret:**
            - `HTTP 200` + empty data → NSE returned OK but no data (weekend/holiday/invalid symbol)
            - `HTTP 401/403` → NSE is rejecting requests from this server
            - `HTTP 429` → Rate limited, wait 60s
            - `Timeout` → Network/NSE slow
            - `nsepython exception` → Library issue, fallback to direct API
            
            **If you see HTTP 403 consistently on weekdays during market hours**, NSE is blocking Streamlit Cloud IPs and we need to either:
            1. Run app locally on your PC (free)
            2. Switch to Kite Connect API (₹500/month)
            """)
    
    st.stop()  # don't continue to analysis on a chain-fetch click


# ----- RUN FULL ANALYSIS -----
if run_analysis:
    if not symbol:
        st.error("Enter a symbol first")
        st.stop()
    
    with st.spinner("Running 360° analysis across 5 layers..."):
        l1 = layer1_macro()
        l2 = layer2_news(symbol, expiry_days)
        l3 = layer3_technical(symbol, option_type)
        l4 = layer4_fundamental(symbol, option_type)
        # Use cached chain if symbol matches, otherwise fetch fresh
        if st.session_state.chain_data and st.session_state.chain_symbol == symbol and st.session_state.chain_data.get("success"):
            chain_data = st.session_state.chain_data
        else:
            chain_data = fetch_option_chain(symbol)
            st.session_state.chain_data = chain_data
            st.session_state.chain_symbol = symbol
        l5 = layer5_option_chain(chain_data, symbol, strike_price, option_type, premium=premium, expiry_days=expiry_days)
    
    composite, verdict, vclass, reason = compute_verdict(l1, l2, l3, l4, l5)
    
    # ----- TRADE SUMMARY HEADER (company name + trade details) -----
    company_name = symbol  # fallback
    current_price = None
    sector = ""
    try:
        info = yf.Ticker(to_yf(symbol)).info
        company_name = info.get("longName") or info.get("shortName") or symbol
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        sector = info.get("sector", "")
    except Exception:
        pass
    
    # Spot from technical layer as fallback
    if not current_price:
        current_price = l3.get("details", {}).get("spot_now") or l3.get("details", {}).get("daily_close")
    
    moneyness = ""
    if current_price:
        if option_type.startswith("CE"):
            if strike_price < current_price * 0.98: moneyness = "🟢 ITM"
            elif strike_price > current_price * 1.02: moneyness = "🔴 OTM"
            else: moneyness = "🟡 ATM"
        else:
            if strike_price > current_price * 1.02: moneyness = "🟢 ITM"
            elif strike_price < current_price * 0.98: moneyness = "🔴 OTM"
            else: moneyness = "🟡 ATM"
    
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0E4D92,#1a6cc4);color:white;padding:18px 24px;border-radius:10px;margin-bottom:14px;">
        <div style="font-size:13px;opacity:0.85;letter-spacing:1px;">ANALYZING TRADE</div>
        <div style="font-size:24px;font-weight:700;margin-top:4px;">{company_name}</div>
        <div style="font-size:14px;opacity:0.9;margin-top:2px;">{symbol} {f"• {sector}" if sector else ""} {f"• Spot ₹{current_price:.2f}" if current_price else ""}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Trade details strip
    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("Option", option_type.split(" ")[0])
    t2.metric("Strike", f"₹{strike_price:,.0f}", moneyness if moneyness else None)
    t3.metric("Premium", f"₹{premium}")
    t4.metric("Expiry", f"{expiry_days}d")
    t5.metric("Capital", f"₹{capital:,.0f}")
    
    st.divider()
    
    # ----- VERDICT BANNER -----
    st.markdown(f'<div class="{vclass}">FINAL VERDICT: {verdict}<br><span style="font-size:14px;font-weight:400">{reason}</span></div>', unsafe_allow_html=True)
    st.markdown(f"### Composite Score: **{composite:.1f} / 100**")
    
    # ----- LAYER SCORE BARS -----
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("L1 Macro", f"{l1['score']}/100", l1.get("regime", ""))
    col2.metric("L2 News/Events", f"{l2['score']}/100")
    col3.metric("L3 Technical", f"{l3['score']}/100", l3.get("bias", ""))
    col4.metric("L4 Fundamental", f"{l4['score']}/100", l4.get("alignment", ""))
    col5.metric("L5 Option Chain", f"{l5['score']}/100", l5.get("health", ""))
    
    st.divider()
    
    # ----- TRADE PLAN (always visible with verdict-specific framing) -----
    plan = build_trade_plan(premium, lot_size, capital, expiry_days, l3)
    
    # Verdict-specific heading
    if "BUY" in verdict:
        st.subheader("📋 Trade Plan — Execute With Discipline")
        st.success("✅ All 4 layers confirm. Plan below is your execution blueprint.")
    elif "HOLD" in verdict:
        st.subheader("📋 Trade Plan — Wait for Trigger")
        st.info("🟡 Setup forming but not confirmed. Plan shown for watchlist. Wait for stronger trigger before entry.")
    else:  # AVOID
        st.subheader("📋 Hypothetical Trade Plan — DO NOT EXECUTE")
        st.error("""
        🚨 **VERDICT IS AVOID — DO NOT TAKE THIS TRADE**  
        
        The plan below is shown for **learning, journaling, and paper-trading only**.  
        Hard vetoes were triggered in the engine. Taking this trade against the framework defeats the entire purpose of 360° reconfirmation.  
        
        **Use this section to:**
        - Understand what the engine *would* have suggested if conditions improved
        - Paper-trade and compare actual outcomes vs. engine logic
        - Refine your scoring weights over time
        """)
    
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
    
    # Reinforce AVOID warning at the bottom
    if "AVOID" in verdict:
        st.error("⛔ Reminder: This trade is flagged AVOID. The plan above is illustrative only.")
    
    st.divider()
    
    # ----- DETAILED LAYER BREAKDOWN -----
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌍 L1 Macro", "📰 L2 News", "📈 L3 Technical", "💰 L4 Fundamental", "🔗 L5 Option Chain"])
    
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
    
    with tab5:
        st.write(f"**Health:** {l5.get('health')}")
        for n in l5.get("notes", []): st.write(n)
        with st.expander("Option chain signals (PCR, Max Pain, OI, IV)"):
            st.json(l5.get("details", {}))
        if l5.get("health") == "Data Unavailable 🟡":
            st.warning("To get the institutional edge from L5, click '📊 Fetch Live Option Chain' in the sidebar first, then run analysis again.")
    
    st.divider()
    st.caption("⚠️ Signal-only tool. Verify all signals against your own analysis. Past performance ≠ future results. Trade at your own risk.")

else:
    st.info("👈 **Standard workflow:** Enter Symbol, Option Type, Strike (from your terminal), Premium (from your terminal), DTE, Capital → click **🚀 RUN 360° ANALYSIS**. Optionally try **📊 Try Fetching Option Chain** for live OI/PCR/MaxPain signals (may fail due to NSE cloud-IP blocking — fallback to manual entry if so).")
    
    st.markdown("""
    ### How the 5-Layer Quintuple Lock Works
    
    **Layer 1 — Macro & Global (20% weight)**  
    Pulls US/Asian markets, India VIX, crude, DXY, USD/INR. Classifies regime as Risk-On / Neutral / Risk-Off. Option buyers need movement — VIX in 13-18 zone is the sweet spot.
    
    **Layer 2 — News & Events (15% weight)**  
    Checks earnings proximity (IV crush risk), recent news flow, sector context. Earnings within expiry window = veto.
    
    **Layer 3 — Technical (30% weight, the heaviest)**  
    Multi-timeframe: Daily (EMA stack, RSI, ADX), 1H (trend alignment), 15m (VWAP + EMA9 entry trigger). Below 50 = hard veto.
    
    **Layer 4 — Fundamental (15% weight)**  
    Quick sanity: earnings growth, ROE, debt, analyst targets, valuation. "Contrary" alignment = hard veto.
    
    **Layer 5 — Option Chain Health (20% weight) 🆕**  
    The institutional edge. Checks PCR, Max Pain magnet, OI buildup at your strike, IV reasonableness vs ATM, and liquidity. Below 35 = hard veto.
    
    **Final Verdict** uses weighted composite + hard veto rules. BUY requires:
    - Composite ≥ 70
    - No hard vetoes
    - Technical ≥ 50
    - Macro ≥ 35
    - Fundamentals not Contrary
    - Option Chain ≥ 35 (if fetched)
    
    💡 **Practical note on L5:** NSE blocks most cloud server IPs (HTTP 403). Layer 5 will usually run in **fallback mode** (yfinance + Black-Scholes for theoretical premium check + HV regime check) on Streamlit Cloud. This still gives you valuable signals (moneyness, overpaying flag, vol regime) — just not PCR/MaxPain/OI. For full L5 access, options are: (a) run app locally on your PC, or (b) use Kite Connect API (₹500/mo). Decide after 2 weeks of paper trading.
    """)
