"""
signal_engine.py — AI Signal Engine with confidence scoring
"""

import requests
import numpy as np


def get_btc_prices(days=60):
    """Fetch BTC daily closing prices — tries multiple sources."""
    sources = [
        ("https://api.binance.com/api/v3/klines",
         {"symbol": "BTCUSDT", "interval": "1d", "limit": days},
         lambda r: [float(c[4]) for c in r.json()]),
        ("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
         {"vs_currency": "usd", "days": days, "interval": "daily"},
         lambda r: [p[1] for p in r.json()["prices"]]),
        ("https://min-api.cryptocompare.com/data/v2/histoday",
         {"fsym": "BTC", "tsym": "USD", "limit": days},
         lambda r: [d["close"] for d in r.json()["Data"]["Data"]]),
    ]
    for url, params, parser in sources:
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            prices = parser(resp)
            if prices:
                return prices
        except Exception as e:
            print(f"Price source failed: {url} — {e}")
            continue
    raise Exception("All price sources failed")


def calc_rsi(prices, period=14):
    d = np.diff(prices)
    gains  = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    avg_g  = np.mean(gains[-period:])
    avg_l  = np.mean(losses[-period:])
    return 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)


def calc_macd(prices):
    p = np.array(prices)
    e12 = float(np.convolve(p, np.ones(12)/12, mode='valid')[-1])
    e26 = float(np.convolve(p, np.ones(26)/26, mode='valid')[-1])
    return round(e12 - e26, 2)


def calc_bollinger(prices, period=20):
    r = np.array(prices[-period:])
    mid = np.mean(r); std = np.std(r)
    return round(mid - 2*std, 2), round(mid, 2), round(mid + 2*std, 2)


def calc_ma(prices, period=20):
    return round(np.mean(prices[-period:]), 2)


def generate_signal() -> dict:
    prices  = get_btc_prices(days=60)
    current = round(prices[-1], 2)
    rsi     = calc_rsi(prices)
    macd    = calc_macd(prices)
    ma20    = calc_ma(prices, 20)
    bb_low, bb_mid, bb_high = calc_bollinger(prices)

    score   = 0
    reasons = []

    if rsi < 30:
        score += 2; reasons.append(f"RSI {rsi} → Oversold 🟢")
    elif rsi > 70:
        score -= 2; reasons.append(f"RSI {rsi} → Overbought 🔴")
    else:
        reasons.append(f"RSI {rsi} → Neutral ⚪")

    if macd > 0:
        score += 1; reasons.append(f"MACD {macd} → Bullish 🟢")
    else:
        score -= 1; reasons.append(f"MACD {macd} → Bearish 🔴")

    if current > ma20:
        score += 1; reasons.append(f"Above MA20 (${ma20:,}) 🟢")
    else:
        score -= 1; reasons.append(f"Below MA20 (${ma20:,}) 🔴")

    if current < bb_low:
        score += 1; reasons.append(f"Below BB lower (${bb_low:,}) → Bounce 🟢")
    elif current > bb_high:
        score -= 1; reasons.append(f"Above BB upper (${bb_high:,}) → Overextended 🔴")
    else:
        reasons.append(f"Inside BB bands (mid ${bb_mid:,}) ⚪")

    confidence = round((score + 5) / 10 * 100, 1)

    if score >= 3:
        direction, label = "up",   "🟢 BET UP"
    elif score <= -3:
        direction, label = "down", "🔴 BET DOWN"
    else:
        direction, label = None,   "⚪ HOLD"

    return {
        "price": current, "rsi": rsi, "macd": macd,
        "ma20": ma20, "bb_low": bb_low, "bb_high": bb_high,
        "score": score, "confidence": confidence,
        "direction": direction, "label": label,
        "reasons": reasons,
        "tradeable": confidence >= 80 and direction is not None,
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
        f"{'✅ Auto-trade will fire!' if sig['tradeable'] else '⏸ Below 80% threshold — waiting'}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)
