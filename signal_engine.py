"""
signal_engine.py — Enhanced 5-min BTC/ETH signal engine
Optimized for 5-minute Myriad candle markets
"""

import requests
import numpy as np


# ── Price Data ────────────────────────────────────────────────────────────────
def get_candles(symbol="BTC", limit=100):
    resp = requests.get(
        "https://min-api.cryptocompare.com/data/v2/histominute",
        params={"fsym": symbol, "tsym": "USD", "limit": limit},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("Data", {}).get("Data", [])


def get_btc_candles(limit=100):
    return get_candles("BTC", limit)


def get_eth_candles(limit=100):
    return get_candles("ETH", limit)


def get_order_book(symbol="BTCUSDT"):
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/depth",
            params={"symbol": symbol, "limit": 20},
            timeout=8
        )
        resp.raise_for_status()
        data    = resp.json()
        bids    = data["bids"]
        asks    = data["asks"]
        bid_vol = sum(float(b[1]) for b in bids)
        ask_vol = sum(float(a[1]) for a in asks)

        # Detect walls — large single orders at round numbers
        top_ask_wall = max((float(a[1]) for a in asks[:5]), default=0)
        top_bid_wall = max((float(b[1]) for b in bids[:5]), default=0)

        return bid_vol, ask_vol, top_bid_wall, top_ask_wall
    except Exception:
        return None, None, 0, 0


def get_funding_rate(symbol="BTCUSDT"):
    """Fetch current funding rate from Binance futures."""
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            params={"symbol": symbol},
            timeout=8
        )
        resp.raise_for_status()
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
    return round(e12 - e26, 2)


def calc_bollinger(closes, period=20):
    r   = np.array(closes[-period:])
    mid = np.mean(r)
    std = np.std(r)
    return round(mid - 2*std, 2), round(mid, 2), round(mid + 2*std, 2)


def calc_vwap(candles, period=20):
    recent    = candles[-period:]
    tp_vol    = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volumefrom"] for c in recent)
    total_vol = sum(c["volumefrom"] for c in recent)
    return round(tp_vol / total_vol, 2) if total_vol > 0 else 0


def calc_momentum(closes, period=5):
    if len(closes) < period + 1:
        return 0
    return round((closes[-1] - closes[-period]) / closes[-period] * 100, 4)


def calc_volume_trend(candles, period=10):
    recent = sum(c["volumefrom"] for c in candles[-period:])
    prev   = sum(c["volumefrom"] for c in candles[-period*2:-period])
    if prev == 0:
        return 0, "Flat"
    ratio = recent / prev
    if ratio > 1.3:
        return ratio, "Rising 📈"
    elif ratio < 0.7:
        return ratio, "Falling 📉"
    return ratio, "Stable ➡️"


def detect_volume_spike(candles, period=10):
    if len(candles) < period + 1:
        return False, 0
    avg_vol = np.mean([c["volumefrom"] for c in candles[-period-1:-1]])
    current = candles[-1]["volumefrom"]
    ratio   = current / avg_vol if avg_vol > 0 else 1
    return ratio > 1.8, round(ratio, 2)


def detect_rsi_divergence(closes, period=14):
    if len(closes) < period * 2:
        return 0, "No divergence ⚪"
    rsi_now      = calc_rsi(closes, period)
    rsi_prev     = calc_rsi(closes[:-5], period)
    price_change = closes[-1] - closes[-6]
    if price_change < 0 and rsi_now > rsi_prev:
        return 1, "Bullish divergence 🟢"
    if price_change > 0 and rsi_now < rsi_prev:
        return -1, "Bearish divergence 🔴"
    return 0, "No divergence ⚪"


def detect_candle_pattern(candles):
    if len(candles) < 3:
        return 0, "Neutral ⚪"
    c  = candles[-1]
    c1 = candles[-2]
    o, h, l, cl  = c["open"], c["high"], c["low"], c["close"]
    body         = abs(cl - o)
    candle_range = h - l if h != l else 0.001
    upper_wick   = h - max(o, cl)
    lower_wick   = min(o, cl) - l

    if cl > o and body > candle_range * 0.6:
        return 1, "Strong bullish candle 🟢"
    if lower_wick > body * 2 and body < candle_range * 0.3:
        return 1, "Hammer — reversal up 🟢"
    if cl > o and c1["close"] < c1["open"] and cl > c1["open"] and o < c1["close"]:
        return 1, "Bullish engulfing 🟢"
    if cl < o and body > candle_range * 0.6:
        return -1, "Strong bearish candle 🔴"
    if upper_wick > body * 2 and body < candle_range * 0.3:
        return -1, "Shooting star 🔴"
    if cl < o and c1["close"] > c1["open"] and cl < c1["open"] and o > c1["close"]:
        return -1, "Bearish engulfing 🔴"
    return 0, "Neutral candle ⚪"


def detect_bb_close_outside(candles, bb_low, bb_high):
    """Detect if last candle CLOSED outside Bollinger Bands — high probability signal."""
    last_close = candles[-1]["close"]
    if last_close < bb_low:
        return 1, "Candle closed below BB lower 🟢"
    if last_close > bb_high:
        return -1, "Candle closed above BB upper 🔴"
    return 0, ""


# ── Main Signal ───────────────────────────────────────────────────────────────
def _generate_signal_from_candles(candles: list, ob_symbol="BTCUSDT",
                                   funding_symbol="BTCUSDT") -> dict:
    closes  = [c["close"] for c in candles]
    current = round(closes[-1], 2)

    # Fetch indicators
    rsi                      = calc_rsi(closes)
    macd                     = calc_macd(closes)
    bb_low, bb_mid, bb_high  = calc_bollinger(closes)
    vwap                     = calc_vwap(candles)
    momentum                 = calc_momentum(closes, 5)
    vol_ratio, vol_trend     = calc_volume_trend(candles)
    vol_spike, spike_ratio   = detect_volume_spike(candles)
    candle_sig, candle_desc  = detect_candle_pattern(candles)
    div_sig, div_desc        = detect_rsi_divergence(closes)
    bb_close_sig, bb_close_desc = detect_bb_close_outside(candles, bb_low, bb_high)
    bid_vol, ask_vol, bid_wall, ask_wall = get_order_book(ob_symbol)
    ob_ratio   = round(bid_vol / ask_vol, 3) if bid_vol and ask_vol else None
    funding    = get_funding_rate(funding_symbol)

    # Distance from VWAP as % — used for combo detection
    vwap_dist  = round((current - vwap) / vwap * 100, 4) if vwap else 0

    score   = 0
    reasons = []
    combos  = []

    # ── RSI (weight: 2) ───────────────────────────────────────────────────────
    if rsi < 33:
        score += 2; reasons.append(f"RSI {rsi} → Oversold 🟢")
    elif rsi > 67:
        score -= 2; reasons.append(f"RSI {rsi} → Overbought 🔴")
    else:
        reasons.append(f"RSI {rsi} → Neutral ⚪")

    # ── VWAP (weight: 2) ──────────────────────────────────────────────────────
    if current > vwap:
        score += 2; reasons.append(f"Price above VWAP (${vwap:,}) 🟢")
    else:
        score -= 2; reasons.append(f"Price below VWAP (${vwap:,}) 🔴")

    # ── Order Book (weight: 2) ────────────────────────────────────────────────
    if ob_ratio:
        if ob_ratio > 1.3:
            score += 2; reasons.append(f"Order book: {ob_ratio}x more bids → Buy pressure 🟢")
        elif ob_ratio < 0.7:
            score -= 2; reasons.append(f"Order book: {ob_ratio}x more asks → Sell pressure 🔴")
        else:
            reasons.append(f"Order book balanced ({ob_ratio}x) ⚪")

        # Detect sell/buy walls
        if ask_wall > bid_wall * 2 and ask_wall > 5:
            score -= 1; reasons.append(f"Large sell wall detected 🔴")
        elif bid_wall > ask_wall * 2 and bid_wall > 5:
            score += 1; reasons.append(f"Large buy wall detected 🟢")

    # ── Bollinger Bands (weight: 2) ───────────────────────────────────────────
    if bb_close_sig == 1:
        score += 2; reasons.append(bb_close_desc)
    elif bb_close_sig == -1:
        score -= 2; reasons.append(bb_close_desc)
    elif current < bb_low:
        score += 1; reasons.append(f"Near BB lower (${bb_low:,}) → Bounce zone 🟢")
    elif current > bb_high:
        score -= 1; reasons.append(f"Near BB upper (${bb_high:,}) → Overextended 🔴")
    else:
        reasons.append(f"Inside BB bands (mid ${bb_mid:,}) ⚪")

    # ── Candle Pattern (weight: 1) ────────────────────────────────────────────
    if candle_sig == 1:
        score += 1; reasons.append(candle_desc)
    elif candle_sig == -1:
        score -= 1; reasons.append(candle_desc)
    else:
        reasons.append(candle_desc)

    # ── RSI Divergence (weight: 1) ────────────────────────────────────────────
    if div_sig == 1:
        score += 1; reasons.append(div_desc)
    elif div_sig == -1:
        score -= 1; reasons.append(div_desc)

    # ── Momentum (weight: 1) ──────────────────────────────────────────────────
    if momentum > 0.05:
        score += 1; reasons.append(f"Momentum +{momentum}% → Bullish 🟢")
    elif momentum < -0.05:
        score -= 1; reasons.append(f"Momentum {momentum}% → Bearish 🔴")
    else:
        reasons.append(f"Momentum {momentum}% → Flat ⚪")

    # ── MACD (weight: 0.5 — secondary filter) ────────────────────────────────
    if macd > 0:
        score += 0.5; reasons.append(f"MACD {macd} → Bullish (secondary) 🟢")
    else:
        score -= 0.5; reasons.append(f"MACD {macd} → Bearish (secondary) 🔴")

    # ── Funding Rate (weight: 1) ──────────────────────────────────────────────
    if funding is not None:
        funding_pct = round(funding * 100, 4)
        if funding <= -0.001:
            score += 1; reasons.append(f"Funding rate {funding_pct}% → Longs squeezed → DOWN likely 🔴")
            score -= 2  # Funding rate negative = bearish override
        elif funding >= 0.001:
            score -= 1; reasons.append(f"Funding rate {funding_pct}% → Shorts squeezed → UP likely 🟢")
            score += 2  # Funding rate positive = bullish override
        else:
            reasons.append(f"Funding rate {funding_pct}% → Neutral ⚪")

    # ── Volume Spike (amplifier) ──────────────────────────────────────────────
    if vol_spike:
        if score > 0:
            score += 1; reasons.append(f"Volume spike {spike_ratio}x → Confirms UP 🟢")
        elif score < 0:
            score -= 1; reasons.append(f"Volume spike {spike_ratio}x → Confirms DOWN 🔴")

    reasons.append(f"Volume trend: {vol_trend}")

    # ── High-probability combos (bonus +1 each) ───────────────────────────────
    if rsi > 67 and vwap_dist > 0.1:
        score -= 1
        combos.append("⚡ COMBO: RSI overbought + far above VWAP → High prob DOWN")
    if rsi < 33 and vwap_dist < -0.1:
        score += 1
        combos.append("⚡ COMBO: RSI oversold + far below VWAP → High prob UP")
    if rsi > 67 and bb_close_sig == -1:
        score -= 1
        combos.append("⚡ COMBO: RSI overbought + closed above BB → Strong DOWN signal")
    if rsi < 33 and bb_close_sig == 1:
        score += 1
        combos.append("⚡ COMBO: RSI oversold + closed below BB → Strong UP signal")
    if rsi > 67 and ob_ratio and ob_ratio < 0.7:
        score -= 1
        combos.append("⚡ COMBO: RSI overbought + sell wall → Very high prob DOWN")

    for c in combos:
        reasons.append(c)

    # ── Confidence ────────────────────────────────────────────────────────────
    max_score  = 14  # max possible with combos and amplifiers
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)
    confidence = max(0, min(100, confidence))

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
        "vwap":       vwap,
        "bb_low":     bb_low,
        "bb_high":    bb_high,
        "momentum":   momentum,
        "ob_ratio":   ob_ratio,
        "funding":    funding,
        "score":      score,
        "confidence": confidence,
        "direction":  direction,
        "label":      label,
        "reasons":    reasons,
        "tradeable":  confidence >= 71 and direction is not None,
    }


def generate_signal() -> dict:
    candles = get_btc_candles(limit=100)
    if not candles:
        raise Exception("No BTC candle data")
    sig = _generate_signal_from_candles(candles, "BTCUSDT", "BTCUSDT")
    sig["asset"] = "BTC"
    return sig


def generate_eth_signal() -> dict:
    candles = get_eth_candles(limit=100)
    if not candles:
        raise Exception("No ETH candle data")
    sig = _generate_signal_from_candles(candles, "ETHUSDT", "ETHUSDT")
    sig["asset"] = "ETH"
    return sig


def format_signal(sig: dict) -> str:
    bar_filled = int(sig["confidence"] / 10)
    bar   = "█" * bar_filled + "░" * (10 - bar_filled)
    asset = sig.get("asset", "BTC")
    funding_text = ""
    if sig.get("funding") is not None:
        funding_text = f"\n💸 Funding   : {round(sig['funding'] * 100, 4)}%"

    lines = [
        f"📊 *{asset} AI Signal*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 Price      : ${sig['price']:,}",
        f"📈 Signal     : {sig['label']}",
        f"🎯 Confidence : {sig['confidence']}%",
        f"   [{bar}]{funding_text}",
        "─────────────────────",
    ]
    for r in sig["reasons"]:
        lines.append(f"  • {r}")
    lines += [
        "─────────────────────",
        f"{'✅ Auto-trade firing!' if sig['tradeable'] else '⏸ Below 71% — waiting for stronger signal'}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)
