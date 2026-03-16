"""
signal_engine.py — Enhanced BTC signal engine using 5-min candles
"""

import requests
import numpy as np


def get_btc_candles(limit=60):
    """Fetch 5-minute BTC candles from CryptoCompare."""
    resp = requests.get(
        "https://min-api.cryptocompare.com/data/v2/histominute",
        params={"fsym": "BTC", "tsym": "USD", "limit": limit},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json().get("Data", {}).get("Data", [])
    return data


# === Legacy Indicators ===

def calc_rsi(closes, period=14):
    closes = np.array(closes)
    d = np.diff(closes)
    gains  = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    avg_g  = np.mean(gains[-period:])
    avg_l  = np.mean(losses[-period:])
    return 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)


def calc_macd(closes):
    p = np.array(closes)
    e12 = float(np.convolve(p, np.ones(12)/12, mode='valid')[-1])
    e26 = float(np.convolve(p, np.ones(26)/26, mode='valid')[-1])
    return round(e12 - e26, 2)


def calc_bollinger(closes, period=20):
    r = np.array(closes[-period:])
    mid = np.mean(r); std = np.std(r)
    return round(mid - 2*std, 2), round(mid, 2), round(mid + 2*std, 2)


def calc_ma(closes, period=20):
    return round(np.mean(closes[-period:]), 2)


def calc_momentum(closes, period=5):
    """Price momentum — rate of change over last N candles."""
    if len(closes) < period + 1:
        return 0
    return round((closes[-1] - closes[-period]) / closes[-period] * 100, 4)


def detect_candle_pattern(candles):
    if len(candles) < 3:
        return 0, "Neutral ⚪"

    c  = candles[-1]
    c1 = candles[-2]

    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    body   = abs(cl - o)
    candle_range = h - l
    upper_wick = h - max(o, cl)
    lower_wick = min(o, cl) - l

    if cl > o and body > candle_range * 0.6:
        return 1, "Strong bullish candle 🟢"
    if lower_wick > body * 2 and body < candle_range * 0.3:
        return 1, "Hammer pattern 🟢"
    if cl > o and c1["close"] < c1["open"] and cl > c1["open"] and o < c1["close"]:
        return 1, "Bullish engulfing 🟢"

    if cl < o and body > candle_range * 0.6:
        return -1, "Strong bearish candle 🔴"
    if upper_wick > body * 2 and body < candle_range * 0.3:
        return -1, "Shooting star 🔴"
    if cl < o and c1["close"] > c1["open"] and cl < c1["open"] and o > c1["close"]:
        return -1, "Bearish engulfing 🔴"

    return 0, "Neutral candle ⚪"


# === New Fast-Reactive Indicators ===

def detect_volume_spike(volumes, period=20):
    if len(volumes) < period + 1:
        return False, 0
    avg_vol = np.mean(volumes[-period-1:-1])
    current = volumes[-1]
    ratio   = current / avg_vol if avg_vol > 0 else 1
    return ratio > 1.8, round(ratio, 2)


def calc_vwap(candles):
    total_vol_price = sum(c["close"] * c["volumefrom"] for c in candles)
    total_vol = sum(c["volumefrom"] for c in candles)
    return total_vol_price / total_vol if total_vol > 0 else candles[-1]["close"]


def calc_momentum_size(candle):
    return (candle["close"] - candle["open"]) / candle["open"] * 100


def detect_order_flow(candles):
    c = candles[-1]
    if c["close"] > c["open"]:
        return c["volumefrom"]
    elif c["close"] < c["open"]:
        return -c["volumefrom"]
    else:
        return 0


# === Signal Generation ===

def generate_signal() -> dict:
    candles = get_btc_candles(limit=60)
    if not candles:
        raise Exception("No candle data returned")

    closes  = [c["close"] for c in candles]
    volumes = [c["volumefrom"] for c in candles]
    current = round(closes[-1], 2)

    rsi      = calc_rsi(closes)
    macd     = calc_macd(closes)
    ma20     = calc_ma(closes, 20)
    bb_low, bb_mid, bb_high = calc_bollinger(closes)
    momentum = calc_momentum(closes, 5)
    vol_spike, vol_ratio = detect_volume_spike(volumes, period=20)
    candle_sig, candle_desc = detect_candle_pattern(candles)
    vwap     = calc_vwap(candles)
    mom_size = calc_momentum_size(candles[-1])
    order_flow_delta = detect_order_flow(candles)

    score   = 0
    reasons = []

    # Legacy TA
    if rsi < 35:
        score += 1; reasons.append(f"RSI {rsi} → Oversold 🟢")
    elif rsi > 65:
        score -= 1; reasons.append(f"RSI {rsi} → Overbought 🔴")
    else:
        reasons.append(f"RSI {rsi} → Neutral ⚪")

    if macd > 0:
        score += 1; reasons.append(f"MACD {macd} → Bullish 🟢")
    else:
        score -= 1; reasons.append(f"MACD {macd} → Bearish 🔴")

    if momentum > 0.05:
        score += 1; reasons.append(f"Momentum +{momentum}% → Bullish 🟢")
    elif momentum < -0.05:
        score -= 1; reasons.append(f"Momentum {momentum}% → Bearish 🔴")
    else:
        reasons.append(f"Momentum {momentum}% → Flat ⚪")

    if current < bb_low:
        score += 1; reasons.append(f"Below BB lower (${bb_low:,}) → Bounce 🟢")
    elif current > bb_high:
        score -= 1; reasons.append(f"Above BB upper (${bb_high:,}) → Overextended 🔴")
    else:
        reasons.append(f"Inside BB bands (mid ${bb_mid:,}) ⚪")

    if candle_sig == 1:
        score += 1; reasons.append(candle_desc)
    elif candle_sig == -1:
        score -= 1; reasons.append(candle_desc)
    else:
        reasons.append(candle_desc)

    # New fast-reacting model
    if vol_spike:
        if score >= 0:
            score += 2; reasons.append(f"Volume spike {vol_ratio}x → Strong UP 🟢")
        else:
            score -= 2; reasons.append(f"Volume spike {vol_ratio}x → Strong DOWN 🔴")

    if order_flow_delta > 0:
        score += 2; reasons.append(f"Order flow +{order_flow_delta:.2f} → Bullish 🟢")
    elif order_flow_delta < 0:
        score -= 2; reasons.append(f"Order flow {order_flow_delta:.2f} → Bearish 🔴")

    if mom_size > 0.12:
        score += 2; reasons.append(f"Candle momentum {mom_size:.3f}% → Strong UP 🟢")
    elif mom_size < -0.12:
        score -= 2; reasons.append(f"Candle momentum {mom_size:.3f}% → Strong DOWN 🔴")

    if current > vwap:
        score += 1; reasons.append(f"Above VWAP → Bullish bias 🟢")
    else:
        score -= 1; reasons.append(f"Below VWAP → Bearish bias 🔴")

    # Confidence scaling
    max_score  = 12
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)

    if score >= 4:
        direction, label = "up",   "🟢 BET UP"
    elif score <= -4:
   # Confidence scaling
    max_score  = 12
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)

    if score >= 4:
        direction, label = "up",   "🟢 BET UP"
    elif score <= -4:
        direction, label = "down", "🔴 BET DOWN"
    else:
        direction, label = None,   "⚪ HOLD"

    return {
        "price":      current,
        "rsi":        rsi,
        "macd":       macd,
        "ma20":       ma20,
        "bb_low":     bb_low,
        "bb_high":    bb_high,
        "momentum":   momentum,
        "mom_size":   mom_size,
        "vol_ratio":  vol_ratio,
        "order_flow": order_flow_delta,
        "vwap":       vwap,
        "score":      score,
        "confidence": confidence,
        "direction":  direction,
        "label":      label,
        "reasons":    reasons,
        "tradeable":  confidence >= 80 and direction is not None,
    }


def format_signal(sig: dict) -> str:
    bar_filled = int(sig["confidence"] / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    lines = [
        "📊 *BTC AI Signal*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 Price      : ${sig['price']:,}",
        f"📈 Signal     : {sig['label']}",
        f"🎯 Confidence : {sig['confidence']}%",
        f"   [{bar}]",
        "─────────────────────",
    ]
    for r in sig["reasons"]:
        lines.append(f"  • {r}")
    lines += [
        "─────────────────────",
        f"{'✅ Auto-trade will fire!' if sig['tradeable'] else '⏸ Below 80% — waiting for stronger signal'}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)
        
