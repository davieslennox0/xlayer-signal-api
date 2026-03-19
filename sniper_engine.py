"""
sniper_engine.py — High-frequency sniper triggers for 5-min BTC/ETH markets
Fires instantly on: order book walls, liquidation cascades, round number bounces
"""

import requests
import numpy as np

BINANCE_API  = "https://api.binance.com"
BINANCE_FAPI = "https://fapi.binance.com"

# Round numbers BTC reacts to
BTC_ROUND_LEVELS = [
    70000, 71000, 72000, 73000, 74000, 75000,
    76000, 77000, 78000, 79000, 80000,
    65000, 66000, 67000, 68000, 69000,
]
ETH_ROUND_LEVELS = [
    2000, 2100, 2200, 2300, 2400, 2500,
    2600, 2700, 2800, 2900, 3000,
    1800, 1900,
]


# ── Data fetchers ─────────────────────────────────────────────────────────────
def get_order_book_deep(symbol="BTCUSDT", limit=50):
    """Fetch deep order book to detect walls."""
    try:
        resp = requests.get(
            f"{BINANCE_API}/api/v3/depth",
            params={"symbol": symbol, "limit": limit},
            timeout=6
        )
        data = resp.json()
        bids = [(float(p), float(q)) for p, q in data["bids"]]
        asks = [(float(p), float(q)) for p, q in data["asks"]]
        return bids, asks
    except Exception:
        return [], []


def get_recent_liquidations(symbol="BTCUSDT"):
    """Fetch recent liquidation orders from Binance futures."""
    try:
        resp = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/forceOrders",
            params={"symbol": symbol, "limit": 20},
            timeout=6
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def get_recent_trades(symbol="BTCUSDT", limit=50):
    """Fetch recent individual trades to detect tape momentum."""
    try:
        resp = requests.get(
            f"{BINANCE_API}/api/v3/trades",
            params={"symbol": symbol, "limit": limit},
            timeout=6
        )
        data = resp.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def get_24h_stats(symbol="BTCUSDT"):
    """Get 24h price stats."""
    try:
        resp = requests.get(
            f"{BINANCE_API}/api/v3/ticker/24hr",
            params={"symbol": symbol},
            timeout=6
        )
        return resp.json()
    except Exception:
        return {}


# ── Sniper Detectors ──────────────────────────────────────────────────────────
def detect_order_book_wall(symbol="BTCUSDT", wall_threshold_usd=300000):
    """
    Detect large buy/sell walls in order book.
    A wall is a single order > $300K USD at a key price level.
    Returns: (score, description)
    score: +2 = strong buy wall (price likely up), -2 = strong sell wall (price likely down)
    """
    bids, asks = get_order_book_deep(symbol, limit=50)
    if not bids or not asks:
        return 0, ""

    current_price = bids[0][0] if bids else 0

    # Find largest single wall in top 20 levels
    max_bid_wall = max(((p * q, p, q) for p, q in bids[:20]), default=(0, 0, 0))
    max_ask_wall = max(((p * q, p, q) for p, q in asks[:20]), default=(0, 0, 0))

    bid_usd = max_bid_wall[0]
    ask_usd = max_ask_wall[0]

    result_score = 0
    result_desc  = ""

    if bid_usd > wall_threshold_usd:
        dist = round(abs(max_bid_wall[1] - current_price) / current_price * 100, 3)
        result_score = 2
        result_desc  = f"🧱 BUY WALL ${bid_usd/1000:.0f}K at ${max_bid_wall[1]:,} ({dist}% away) → Price support 🟢"

    if ask_usd > wall_threshold_usd and ask_usd > bid_usd:
        dist = round(abs(max_ask_wall[1] - current_price) / current_price * 100, 3)
        result_score = -2
        result_desc  = f"🧱 SELL WALL ${ask_usd/1000:.0f}K at ${max_ask_wall[1]:,} ({dist}% away) → Price resistance 🔴"

    return result_score, result_desc


def detect_liquidation_cascade(symbol="BTCUSDT", threshold_usd=500000):
    """
    Detect recent liquidation cascade.
    Large liquidations = forced selling/buying = price reversal incoming.
    Returns: (score, description)
    score: +3 = large long liquidations (price bottomed, bounce UP)
           -3 = large short liquidations (price topped, dump DOWN)
    """
    liqs = get_recent_liquidations(symbol)
    if not liqs:
        return 0, ""

    long_liqs  = sum(float(l.get("origQty", 0)) * float(l.get("price", 0))
                    for l in liqs if l.get("side") == "SELL")  # long liq = sell
    short_liqs = sum(float(l.get("origQty", 0)) * float(l.get("price", 0))
                    for l in liqs if l.get("side") == "BUY")   # short liq = buy

    if long_liqs > threshold_usd:
        return 3, f"💥 LIQUIDATION CASCADE: ${long_liqs/1000:.0f}K longs liquidated → Bounce UP incoming 🟢"
    if short_liqs > threshold_usd:
        return -3, f"💥 LIQUIDATION CASCADE: ${short_liqs/1000:.0f}K shorts liquidated → Dump DOWN incoming 🔴"

    return 0, ""


def detect_round_number(symbol="BTCUSDT", threshold_pct=0.15):
    """
    Detect if price is near a key round number.
    Price within 0.15% of round number = high reaction probability.
    Returns: (score, description)
    """
    try:
        resp = requests.get(
            f"{BINANCE_API}/api/v3/ticker/price",
            params={"symbol": symbol},
            timeout=6
        )
        price = float(resp.json()["price"])
    except Exception:
        return 0, ""

    levels = BTC_ROUND_LEVELS if "BTC" in symbol else ETH_ROUND_LEVELS

    for level in levels:
        dist_pct = abs(price - level) / level * 100
        if dist_pct <= threshold_pct:
            if price < level:
                # Approaching from below — resistance
                return -1, f"🎯 ROUND NUMBER: ${price:,} near ${level:,} resistance → Rejection risk 🔴"
            else:
                # Just broke above — support
                return 1, f"🎯 ROUND NUMBER: ${price:,} above ${level:,} support → Bounce likely 🟢"

    return 0, ""


def detect_tape_momentum(symbol="BTCUSDT", lookback=30):
    """
    Tape reading — detect consecutive buy or sell dominance in recent trades.
    Returns: (score, description)
    """
    trades = get_recent_trades(symbol, limit=lookback)
    if not trades:
        return 0, ""

    buys  = sum(1 for t in trades if not t.get("isBuyerMaker"))
    sells = sum(1 for t in trades if t.get("isBuyerMaker"))
    total = len(trades)

    buy_pct  = buys / total * 100
    sell_pct = sells / total * 100

    if buy_pct >= 75:
        return 1, f"📈 TAPE: {buy_pct:.0f}% buy trades in last {lookback} → Strong buying pressure 🟢"
    if sell_pct >= 75:
        return -1, f"📉 TAPE: {sell_pct:.0f}% sell trades in last {lookback} → Strong selling pressure 🔴"

    return 0, ""


# ── Main Sniper Signal ────────────────────────────────────────────────────────
def generate_sniper_signal(asset="BTC") -> dict:
    """
    Run all sniper detectors and return combined signal.
    Fast — designed to run every 60 seconds.
    """
    symbol    = f"{asset}USDT"
    score     = 0
    triggers  = []
    reasons   = []

    # Order book wall (weight: ±2)
    wall_score, wall_desc = detect_order_book_wall(symbol)
    if wall_score != 0:
        score += wall_score
        triggers.append(wall_desc)

    # Liquidation cascade (weight: ±3)
    liq_score, liq_desc = detect_liquidation_cascade(symbol)
    if liq_score != 0:
        score += liq_score
        triggers.append(liq_desc)

    # Round number (weight: ±1)
    rn_score, rn_desc = detect_round_number(symbol)
    if rn_score != 0:
        score += rn_score
        triggers.append(rn_desc)

    # Tape momentum (weight: ±1)
    tape_score, tape_desc = detect_tape_momentum(symbol)
    if tape_score != 0:
        score += tape_score
        reasons.append(tape_desc)

    # Confidence mapping
    max_score  = 7
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)
    confidence = max(0, min(100, confidence))

    if score >= 2:
        direction, label = "up",   "🟢 SNIPE UP"
    elif score <= -2:
        direction, label = "down", "🔴 SNIPE DOWN"
    else:
        direction, label = None,   "⚪ NO SNIPE"

    return {
        "asset":      asset,
        "score":      score,
        "confidence": confidence,
        "direction":  direction,
        "label":      label,
        "triggers":   triggers,
        "reasons":    reasons,
        "tradeable":  direction is not None,
        "mode":       "sniper",
    }


def format_sniper_signal(sig: dict) -> str:
    lines = [
        f"⚡ *{sig['asset']} Sniper Signal*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Signal     : {sig['label']}",
        f"🎯 Score      : {sig['score']}/7",
    ]
    if sig["triggers"]:
        lines.append("🔫 *Sniper Triggers:*")
        for t in sig["triggers"]:
            lines.append(f"  {t}")
    if sig["reasons"]:
        for r in sig["reasons"]:
            lines.append(f"  • {r}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{'🔫 SNIPE FIRING!' if sig['tradeable'] else '👁 Watching...'}") 
    return "\n".join(lines)
