"""
signal_engine.py — Short-term BTC signal engine using 5-min candles
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


def detect_volume_spike(volumes, period=10):
    """Detect if current volume is significantly above average."""
    if len(volumes) < period + 1:
        return False, 0
    avg_vol = np.mean(volumes[-period-1:-1])
    current = volumes[-1]
    ratio   = current / avg_vol if avg_vol > 0 else 1
    return ratio > 1.5, round(ratio, 2)


def detect_candle_pattern(candles):
    """
    Detect basic bullish/bearish candle patterns.
    Returns: (signal, description)
    signal: 1=bullish, -1=bearish, 0=neutral
    """
    if len(candles) < 3:
        return 0, "Neutral ⚪"

    c  = candles[-1]
    c1 = candles[-2]
    c2 = candles[-3]

    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    body   = abs(cl - o)
    candle_range = h - l
    upper_wick = h - max(o, cl)
    lower_wick = min(o, cl) - l

    # Bullish patterns
    if cl > o and body > candle_range * 0.6:
        return 1, "Strong bullish candle 🟢"

    if lower_wick > body * 2 and body < candle_range * 0.3:
        return 1, "Hammer pattern 🟢"

    if cl > o and c1["close"] < c1["open"] and cl > c1["open"] and o < c1["close"]:
        return 1, "Bullish engulfing 🟢"

    # Bearish patterns
    if cl < o and body > candle_range * 0.6:
        return -1, "Strong bearish candle 🔴"

    if upper_wick > body * 2 and body < candle_range * 0.3:
        return -1, "Shooting star 🔴"

    if cl < o and c1["close"] > c1["open"] and cl < c1["open"] and o > c1["close"]:
        return -1, "Bearish engulfing 🔴"

    return 0, "Neutral candle ⚪"


def generate_signal() -> dict:
    candles = get_btc_candles(limit=60)
    if not candles:
        raise Exception("No candle data returned")

    closes  = [c["close"] for c in candles]
    volumes = [c["volumefrom"] for c in candles]
    current = round(closes[-1], 2)

    # Indicators
    rsi      = calc_rsi(closes)
    macd     = calc_macd(closes)
    ma20     = calc_ma(closes, 20)
    bb_low, bb_mid, bb_high = calc_bollinger(closes)
    momentum = calc_momentum(closes, 5)
    vol_spike, vol_ratio = detect_volume_spike(volumes)
    candle_sig, candle_desc = detect_candle_pattern(candles)

    score   = 0
    reasons = []

    # RSI (weight: 2)
    if rsi < 35:
        score += 2; reasons.append(f"RSI {rsi} → Oversold 🟢")
    elif rsi > 65:
        score -= 2; reasons.append(f"RSI {rsi} → Overbought 🔴")
    else:
        reasons.append(f"RSI {rsi} → Neutral ⚪")

    # MACD (weight: 1)
    if macd > 0:
        score += 1; reasons.append(f"MACD {macd} → Bullish 🟢")
    else:
        score -= 1; reasons.append(f"MACD {macd} → Bearish 🔴")

    # Momentum (weight: 1)
    if momentum > 0.05:
        score += 1; reasons.append(f"Momentum +{momentum}% → Bullish 🟢")
    elif momentum < -0.05:
        score -= 1; reasons.append(f"Momentum {momentum}% → Bearish 🔴")
    else:
        reasons.append(f"Momentum {momentum}% → Flat ⚪")

    # Bollinger (weight: 1)
    if current < bb_low:
        score += 1; reasons.append(f"Below BB lower (${bb_low:,}) → Bounce 🟢")
    elif current > bb_high:
        score -= 1; reasons.append(f"Above BB upper (${bb_high:,}) → Overextended 🔴")
    else:
        reasons.append(f"Inside BB bands (mid ${bb_mid:,}) ⚪")

    # Candle pattern (weight: 1)
    if candle_sig == 1:
        score += 1; reasons.append(candle_desc)
    elif candle_sig == -1:
        score -= 1; reasons.append(candle_desc)
    else:
        reasons.append(candle_desc)

    # Volume spike (bonus weight: 1 — amplifies direction)
    if vol_spike:
        if score > 0:
            score += 1; reasons.append(f"Volume spike {vol_ratio}x → Confirms UP 🟢")
        elif score < 0:
            score -= 1; reasons.append(f"Volume spike {vol_ratio}x → Confirms DOWN 🔴")

    # Map score to confidence
    max_score  = 7  # max possible with volume bonus
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)

    if score >= 3:
        direction, label = "up",   "🟢 BET UP"
    elif score <= -3:
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
