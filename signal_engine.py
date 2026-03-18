"""
signal_engine.py — PolySnipe-style 5-min signal engine
Asymmetric bias, regime switch, volume trap, divergence multiplier
"""

import requests
import numpy as np


# ── Data fetchers ─────────────────────────────────────────────────────────────
def get_candles(symbol="BTC", limit=100):
    resp = requests.get(
        "https://min-api.cryptocompare.com/data/v2/histominute",
        params={"fsym": symbol, "tsym": "USD", "limit": limit},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("Data", {}).get("Data", [])

def get_btc_candles(limit=100): return get_candles("BTC", limit)
def get_eth_candles(limit=100): return get_candles("ETH", limit)

def get_order_book(symbol="BTCUSDT"):
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/depth",
            params={"symbol": symbol, "limit": 20}, timeout=8
        )
        data    = resp.json()
        bid_vol = sum(float(b[1]) for b in data["bids"])
        ask_vol = sum(float(a[1]) for a in data["asks"])
        top_ask = max((float(a[1]) for a in data["asks"][:5]), default=0)
        top_bid = max((float(b[1]) for b in data["bids"][:5]), default=0)
        return bid_vol, ask_vol, top_bid, top_ask
    except Exception:
        return None, None, 0, 0

def get_funding_rate(symbol="BTCUSDT"):
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            params={"symbol": symbol}, timeout=8
        )
        return float(resp.json().get("lastFundingRate", 0))
    except Exception:
        return None


# ── Indicators ────────────────────────────────────────────────────────────────
def calc_rsi(closes, period=14):
    d      = np.diff(closes)
    gains  = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    avg_g  = np.mean(gains[-period:])
    avg_l  = np.mean(losses[-period:])
    return 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)

def calc_macd(closes):
    p   = np.array(closes)
    e12 = float(np.convolve(p, np.ones(12)/12, mode='valid')[-1])
    e26 = float(np.convolve(p, np.ones(26)/26, mode='valid')[-1])
    macd = e12 - e26
    # Signal line (9-period EMA approximation)
    signal = float(np.convolve(p[-35:], np.ones(9)/9, mode='valid')[-1])
    return round(macd, 4), round(e12 - signal, 4)

def calc_bollinger(closes, period=20):
    r   = np.array(closes[-period:])
    mid = np.mean(r)
    std = np.std(r)
    upper = mid + 2*std
    lower = mid - 2*std
    bandwidth = round((upper - lower) / mid * 100, 4)
    return round(lower, 2), round(mid, 2), round(upper, 2), bandwidth

def calc_bb_bandwidth_trend(closes, period=20, lookback=5):
    """Check if BB bandwidth is expanding or contracting."""
    recent_bw = []
    for i in range(lookback, 0, -1):
        subset = closes[-(period+i):-i]
        if len(subset) >= period:
            r   = np.array(subset)
            mid = np.mean(r)
            std = np.std(r)
            bw  = (mid + 2*std - (mid - 2*std)) / mid * 100
            recent_bw.append(bw)
    if len(recent_bw) < 2:
        return "unknown"
    if recent_bw[-1] > recent_bw[0] * 1.05:
        return "expanding"
    elif recent_bw[-1] < recent_bw[0] * 0.95:
        return "contracting"
    return "ranging"

def calc_vwap(candles, period=20):
    recent    = candles[-period:]
    tp_vol    = sum(((c["high"]+c["low"]+c["close"])/3)*c["volumefrom"] for c in recent)
    total_vol = sum(c["volumefrom"] for c in recent)
    return round(tp_vol/total_vol, 2) if total_vol > 0 else 0

def calc_momentum(closes, period=5):
    if len(closes) < period+1:
        return 0
    return round((closes[-1]-closes[-period])/closes[-period]*100, 4)

def detect_volume_trap(candles, bb_low, bb_high, period=20):
    """
    Volume Trap: Volume > 2x average AND price at BB extreme.
    Returns: (score, description)
    score: +3 = aggressive long, -3 = aggressive short, 0 = no trap
    """
    vols    = [c["volumefrom"] for c in candles]
    avg_vol = np.mean(vols[-period-1:-1])
    cur_vol = vols[-1]
    cur_price = candles[-1]["close"]

    if avg_vol == 0:
        return 0, ""

    ratio = cur_vol / avg_vol
    if ratio > 2.0:
        if cur_price >= bb_high:
            return -3, f"⚡ VOLUME TRAP: {ratio:.1f}x vol at BB top → Blow-off SHORT 🔴"
        elif cur_price <= bb_low:
            return +3, f"⚡ VOLUME TRAP: {ratio:.1f}x vol at BB bottom → Panic bottom LONG 🟢"
    return 0, ""

def detect_rsi_divergence(closes, period=14):
    if len(closes) < period*2:
        return 0
    rsi_now  = calc_rsi(closes, period)
    rsi_prev = calc_rsi(closes[:-5], period)
    price_chg = closes[-1] - closes[-6]
    if price_chg < 0 and rsi_now > rsi_prev:
        return 1   # Bullish divergence
    if price_chg > 0 and rsi_now < rsi_prev:
        return -1  # Bearish divergence
    return 0

def detect_candle_pattern(candles):
    if len(candles) < 3:
        return 0, "Neutral ⚪"
    c  = candles[-1]
    c1 = candles[-2]
    o, h, l, cl  = c["open"], c["high"], c["low"], c["close"]
    body         = abs(cl-o)
    rng          = h-l if h!=l else 0.001
    upper_wick   = h-max(o,cl)
    lower_wick   = min(o,cl)-l

    if cl > o and body > rng*0.6:
        return 1, "Strong bullish candle 🟢"
    if lower_wick > body*2 and body < rng*0.3:
        return 1, "Hammer 🟢"
    if cl > o and c1["close"] < c1["open"] and cl > c1["open"] and o < c1["close"]:
        return 1, "Bullish engulfing 🟢"
    if cl < o and body > rng*0.6:
        return -1, "Strong bearish candle 🔴"
    if upper_wick > body*2 and body < rng*0.3:
        return -1, "Shooting star 🔴"
    if cl < o and c1["close"] > c1["open"] and cl < c1["open"] and o > c1["close"]:
        return -1, "Bearish engulfing 🔴"
    return 0, "Neutral candle ⚪"


# ── Main Signal ───────────────────────────────────────────────────────────────
def _generate_signal_from_candles(candles, ob_symbol="BTCUSDT", funding_symbol="BTCUSDT"):
    closes  = [c["close"] for c in candles]
    current = round(closes[-1], 2)

    # Core calculations
    rsi                          = calc_rsi(closes)
    macd_val, macd_signal        = calc_macd(closes)
    bb_low, bb_mid, bb_high, bw  = calc_bollinger(closes)
    bb_regime                    = calc_bb_bandwidth_trend(closes)
    vwap                         = calc_vwap(candles)
    momentum                     = calc_momentum(closes, 5)
    candle_sig, candle_desc      = detect_candle_pattern(candles)
    div_sig                      = detect_rsi_divergence(closes)
    trap_score, trap_desc        = detect_volume_trap(candles, bb_low, bb_high)
    bid_vol, ask_vol, bid_wall, ask_wall = get_order_book(ob_symbol)
    ob_ratio                     = round(bid_vol/ask_vol, 3) if bid_vol and ask_vol else None
    funding                      = get_funding_rate(funding_symbol)
    vwap_dist                    = round((current-vwap)/vwap*100, 4) if vwap else 0

    bias  = 0.0
    reasons = []
    triggers = []

    # ── 1. ASYMMETRIC RSI BIAS (weight: ±2) ──────────────────────────────────
    if rsi < 35:
        bias += 2
        triggers.append(f"RSI Bias: {rsi} (Zone < 35) → [+2 Bias] 🟢")
    elif rsi > 65:
        bias -= 2
        triggers.append(f"RSI Bias: {rsi} (Zone > 65) → [-2 Bias] 🔴")
    else:
        reasons.append(f"RSI {rsi} → Neutral zone ⚪")

    # ── 2. VOLUME TRAP (weight: ±3 — highest priority) ───────────────────────
    if trap_score != 0:
        bias += trap_score
        triggers.append(trap_desc)

    # ── 3. REGIME SWITCH ─────────────────────────────────────────────────────
    if bb_regime == "ranging":
        # Ranging market: prioritize BB touches + RSI, ignore MACD crossover
        reasons.append(f"Market Mode: Ranging → Prioritize BB/RSI reversion")
        if current <= bb_low:
            bias += 2
            triggers.append(f"Ranging + Price at BB lower → Reversal UP 🟢")
        elif current >= bb_high:
            bias -= 2
            triggers.append(f"Ranging + Price at BB upper → Reversal DOWN 🔴")
        # MACD ignored in ranging mode
    else:
        # Trending market: prioritize MACD + VWAP, ignore BB reversal signals
        reasons.append(f"Market Mode: Trending ({bb_regime}) → Prioritize MACD/VWAP")
        if macd_val > 0 and macd_signal > 0:
            bias += 1.5
            triggers.append(f"Trending + MACD bullish crossover → UP 🟢")
        elif macd_val < 0 and macd_signal < 0:
            bias -= 1.5
            triggers.append(f"Trending + MACD bearish crossover → DOWN 🔴")
        # VWAP bounce in trend
        if current > vwap and vwap_dist > 0.05:
            bias += 1
            triggers.append(f"Trending + Above VWAP (${vwap:,}) → UP 🟢")
        elif current < vwap and vwap_dist < -0.05:
            bias -= 1
            triggers.append(f"Trending + Below VWAP (${vwap:,}) → DOWN 🔴")

    # ── 4. DIVERGENCE MULTIPLIER (only amplifies, never triggers alone) ───────
    if div_sig != 0:
        # Only counts if RSI is already in bias zone OR price touched BB band
        at_bb   = current <= bb_low or current >= bb_high
        rsi_zone = rsi < 35 or rsi > 65
        if at_bb or rsi_zone:
            bias += div_sig
            if div_sig > 0:
                triggers.append(f"Divergence multiplier: Bullish confirmation +1 🟢")
            else:
                triggers.append(f"Divergence multiplier: Bearish confirmation -1 🔴")
        else:
            reasons.append(f"Divergence detected but outside bias zones — ignored ⚪")

    # ── 5. ORDER BOOK PRESSURE (weight: ±1) ──────────────────────────────────
    if ob_ratio:
        if ob_ratio > 1.3:
            bias += 1
            reasons.append(f"Order book: {ob_ratio}x more bids → Buy pressure 🟢")
        elif ob_ratio < 0.7:
            bias -= 1
            reasons.append(f"Order book: {ob_ratio}x more asks → Sell pressure 🔴")
        if ask_wall > bid_wall*2 and ask_wall > 5:
            bias -= 0.5
            reasons.append(f"Sell wall detected 🔴")
        elif bid_wall > ask_wall*2 and bid_wall > 5:
            bias += 0.5
            reasons.append(f"Buy wall detected 🟢")

    # ── 6. CANDLE PATTERN (weight: ±1) ───────────────────────────────────────
    if candle_sig != 0:
        bias += candle_sig
        reasons.append(candle_desc)
    else:
        reasons.append(candle_desc)

    # ── 7. MOMENTUM (weight: ±0.5) ───────────────────────────────────────────
    if momentum > 0.05:
        bias += 0.5
        reasons.append(f"Momentum +{momentum}% → Bullish 🟢")
    elif momentum < -0.05:
        bias -= 0.5
        reasons.append(f"Momentum {momentum}% → Bearish 🔴")
    else:
        reasons.append(f"Momentum {momentum}% → Flat ⚪")

    # ── 8. FUNDING RATE OVERRIDE (weight: ±1) ────────────────────────────────
    if funding is not None:
        fp = round(funding*100, 4)
        if funding <= -0.001:
            bias -= 1
            reasons.append(f"Funding {fp}% → Longs squeezed → bearish 🔴")
        elif funding >= 0.001:
            bias += 1
            reasons.append(f"Funding {fp}% → Shorts squeezed → bullish 🟢")
        else:
            reasons.append(f"Funding {fp}% → Neutral ⚪")

    # ── Confidence mapping ────────────────────────────────────────────────────
    max_bias   = 11.0  # max possible score
    confidence = round((bias + max_bias) / (max_bias * 2) * 100, 1)
    confidence = max(0, min(100, confidence))

    if bias >= 3:
        direction, label, aggression = "up",   "🟢 BUY (UP)",  "Aggressive" if bias >= 5 else "Normal"
    elif bias <= -3:
        direction, label, aggression = "down", "🔴 SELL (DOWN)", "Aggressive" if bias <= -5 else "Normal"
    else:
        direction, label, aggression = None,   "⚪ HOLD", "—"

    return {
        "price":      current,
        "rsi":        rsi,
        "macd":       macd_val,
        "vwap":       vwap,
        "bb_low":     bb_low,
        "bb_high":    bb_high,
        "bb_regime":  bb_regime,
        "bw":         bw,
        "momentum":   momentum,
        "ob_ratio":   ob_ratio,
        "funding":    funding,
        "bias":       bias,
        "confidence": confidence,
        "direction":  direction,
        "label":      label,
        "aggression": aggression,
        "triggers":   triggers,
        "reasons":    reasons,
        "tradeable":  confidence >= 65 and direction is not None,
    }


def generate_signal() -> dict:
    candles = get_btc_candles(limit=100)
    if not candles:
        raise Exception("No BTC data")
    sig = _generate_signal_from_candles(candles, "BTCUSDT", "BTCUSDT")
    sig["asset"] = "BTC"
    return sig


def generate_eth_signal() -> dict:
    candles = get_eth_candles(limit=100)
    if not candles:
        raise Exception("No ETH data")
    sig = _generate_signal_from_candles(candles, "ETHUSDT", "ETHUSDT")
    sig["asset"] = "ETH"
    return sig


def format_signal(sig: dict) -> str:
    bar   = "█" * int(sig["confidence"]/10) + "░" * (10 - int(sig["confidence"]/10))
    asset = sig.get("asset", "BTC")
    fp    = f"{round(sig['funding']*100, 4)}%" if sig.get("funding") is not None else "N/A"
    mode  = sig.get("bb_regime", "unknown").capitalize()

    lines = [
        f"📊 *{asset} AI Signal*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 Price      : ${sig['price']:,}",
        f"📈 Signal     : {sig['label']}",
        f"🎯 Confidence : {sig['confidence']}% [{bar}]",
        f"⚡ Aggression : {sig.get('aggression','—')}",
        f"📡 Mode       : {mode} | Funding: {fp}",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if sig["triggers"]:
        lines.append("⚡ *CRITICAL TRIGGERS:*")
        for t in sig["triggers"]:
            lines.append(f"  {t}")
        lines.append("─────────────────────")

    if sig["reasons"]:
        lines.append("📋 *Supporting Signals:*")
        for r in sig["reasons"]:
            lines.append(f"  • {r}")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{'✅ Auto-trade firing!' if sig['tradeable'] else '⏸ Below 65% — scanning...'}",
    ]
    return "\n".join(lines)
