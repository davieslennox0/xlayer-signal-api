"""
sniper_engine.py — High-frequency sniper triggers
Uses Kraken + Bybit APIs (no geo-blocking)
Detectors: order book walls, liquidation cascade, round numbers, tape momentum
"""

import requests
import numpy as np

KRAKEN_API = "https://api.kraken.com/0/public"
BYBIT_API  = "https://api.bybit.com/v5/market"

# Round number levels
BTC_ROUND_LEVELS = [
    65000, 66000, 67000, 68000, 69000, 70000,
    71000, 72000, 73000, 74000, 75000,
    76000, 77000, 78000, 79000, 80000,
]
ETH_ROUND_LEVELS = [
    1800, 1900, 2000, 2100, 2200, 2300,
    2400, 2500, 2600, 2700, 2800, 2900, 3000,
]

KRAKEN_SYMBOLS = {"BTC": "XBTUSD", "ETH": "ETHUSD"}
BYBIT_SYMBOLS  = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}


# ── Data fetchers ─────────────────────────────────────────────────────────────
def get_order_book(asset="BTC", limit=25):
    """Fetch order book from Kraken."""
    try:
        symbol = KRAKEN_SYMBOLS.get(asset, "XBTUSD")
        resp   = requests.get(
            f"{KRAKEN_API}/Depth",
            params={"pair": symbol, "count": limit},
            timeout=8
        )
        data   = resp.json()
        if data.get("error"):
            return [], []
        result = list(data["result"].values())[0]
        bids   = [(float(p), float(q)) for p, q, _ in result["bids"]]
        asks   = [(float(p), float(q)) for p, q, _ in result["asks"]]
        return bids, asks
    except Exception:
        return [], []


def get_recent_trades(asset="BTC", limit=50):
    """Fetch recent trades from Kraken."""
    try:
        symbol = KRAKEN_SYMBOLS.get(asset, "XBTUSD")
        resp   = requests.get(
            f"{KRAKEN_API}/Trades",
            params={"pair": symbol, "count": limit},
            timeout=8
        )
        data = resp.json()
        if data.get("error"):
            return []
        result = list(data["result"].values())[0]
        # Each trade: [price, volume, time, buy/sell, market/limit, misc]
        trades = [{"price": float(t[0]), "volume": float(t[1]),
                   "side": t[3]} for t in result]
        return trades
    except Exception:
        return []


def get_klines(asset="BTC", interval="1", limit=20):
    """Fetch 1-minute klines from Bybit."""
    try:
        symbol = BYBIT_SYMBOLS.get(asset, "BTCUSDT")
        resp   = requests.get(
            f"{BYBIT_API}/kline",
            params={"category": "linear", "symbol": symbol,
                    "interval": interval, "limit": limit},
            timeout=8
        )
        data = resp.json()
        if data.get("retCode") != 0:
            return []
        candles = []
        for k in data["result"]["list"]:
            candles.append({
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[5]),
            })
        return list(reversed(candles))  # oldest first
    except Exception:
        return []


def get_current_price(asset="BTC"):
    """Get current price from Bybit."""
    try:
        symbol = BYBIT_SYMBOLS.get(asset, "BTCUSDT")
        resp   = requests.get(
            f"{BYBIT_API}/tickers",
            params={"category": "linear", "symbol": symbol},
            timeout=6
        )
        data = resp.json()
        if data.get("retCode") != 0:
            return 0
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception:
        return 0


def get_liquidations(asset="BTC", limit=50):
    """Fetch recent liquidations from Bybit."""
    try:
        symbol = BYBIT_SYMBOLS.get(asset, "BTCUSDT")
        resp   = requests.get(
            f"{BYBIT_API}/liquidation",
            params={"category": "linear", "symbol": symbol, "limit": limit},
            timeout=8
        )
        data = resp.json()
        if data.get("retCode") != 0:
            return []
        return data["result"]["list"]
    except Exception:
        return []


# ── Sniper Detectors ──────────────────────────────────────────────────────────
def detect_order_book_wall(asset="BTC", wall_threshold_usd=150000):
    """
    Detect large buy/sell walls.
    A wall = single order > $150K at a key price level.
    """
    bids, asks = get_order_book(asset)
    if not bids or not asks:
        return 0, ""

    current = bids[0][0] if bids else 0

    max_bid = max(((p * q, p, q) for p, q in bids[:20]), default=(0, 0, 0))
    max_ask = max(((p * q, p, q) for p, q in asks[:20]), default=(0, 0, 0))

    bid_usd = max_bid[0]
    ask_usd = max_ask[0]

    if ask_usd > wall_threshold_usd and ask_usd > bid_usd:
        dist = round(abs(max_ask[1] - current) / current * 100, 3)
        return -2, f"🧱 SELL WALL ${ask_usd/1000:.0f}K at ${max_ask[1]:,} ({dist}% away) → Resistance 🔴"

    if bid_usd > wall_threshold_usd:
        dist = round(abs(max_bid[1] - current) / current * 100, 3)
        return 2, f"🧱 BUY WALL ${bid_usd/1000:.0f}K at ${max_bid[1]:,} ({dist}% away) → Support 🟢"

    return 0, ""


def detect_liquidation_cascade(asset="BTC"):
    """
    Detect liquidation cascade using:
    1. Bybit liquidation feed (direct)
    2. Kline volume spike fallback
    """
    # Try Bybit liquidations first
    liqs = get_liquidations(asset)
    if liqs:
        try:
            long_liqs  = sum(float(l["size"]) * float(l["price"])
                            for l in liqs if l.get("side") == "Buy")   # Buy = short liq
            short_liqs = sum(float(l["size"]) * float(l["price"])
                            for l in liqs if l.get("side") == "Sell")  # Sell = long liq

            if short_liqs > 200000:
                return 3, f"💥 CASCADE: ${short_liqs/1000:.0f}K longs liquidated → Bounce UP 🟢"
            if long_liqs > 200000:
                return -3, f"💥 CASCADE: ${long_liqs/1000:.0f}K shorts liquidated → Dump DOWN 🔴"
        except Exception:
            pass

    # Fallback: volume spike on klines
    candles = get_klines(asset, interval="1", limit=20)
    if len(candles) < 5:
        return 0, ""

    avg_vol    = np.mean([c["volume"] for c in candles[-16:-1]])
    last       = candles[-1]
    cur_vol    = last["volume"]
    price_move = (last["close"] - last["open"]) / last["open"] * 100 if last["open"] > 0 else 0

    if avg_vol == 0:
        return 0, ""

    vol_ratio = cur_vol / avg_vol

    if vol_ratio >= 3.0:
        if price_move <= -0.3:
            return 3, f"💥 VOL CASCADE: {vol_ratio:.1f}x vol + {price_move:.2f}% drop → Long liq → UP 🟢"
        elif price_move >= 0.3:
            return -3, f"💥 VOL CASCADE: {vol_ratio:.1f}x vol + +{price_move:.2f}% spike → Short liq → DOWN 🔴"

    if vol_ratio >= 2.0:
        if price_move <= -0.2:
            return 1, f"⚠️ Vol surge {vol_ratio:.1f}x + drop → Possible long liq 🟢"
        elif price_move >= 0.2:
            return -1, f"⚠️ Vol surge {vol_ratio:.1f}x + spike → Possible short liq 🔴"

    return 0, ""


def detect_round_number(asset="BTC", threshold_pct=0.15):
    """Detect if price is near a key round number."""
    price  = get_current_price(asset)
    if price == 0:
        return 0, ""

    levels = BTC_ROUND_LEVELS if asset == "BTC" else ETH_ROUND_LEVELS

    for level in levels:
        dist_pct = abs(price - level) / level * 100
        if dist_pct <= threshold_pct:
            if price < level:
                return -1, f"🎯 ROUND: ${price:,} near ${level:,} resistance → Rejection risk 🔴"
            else:
                return 1, f"🎯 ROUND: ${price:,} above ${level:,} support → Bounce likely 🟢"

    return 0, ""


def detect_tape_momentum(asset="BTC", lookback=50):
    """Detect buy/sell dominance in recent trades."""
    trades = get_recent_trades(asset, limit=lookback)
    if not trades:
        return 0, ""

    buys  = sum(1 for t in trades if t.get("side") == "b")  # Kraken: b=buy
    sells = sum(1 for t in trades if t.get("side") == "s")
    total = len(trades)
    if total == 0:
        return 0, ""

    buy_pct  = buys / total * 100
    sell_pct = sells / total * 100

    if buy_pct >= 70:
        return 1, f"📈 TAPE: {buy_pct:.0f}% buys in last {total} trades → Buying pressure 🟢"
    if sell_pct >= 70:
        return -1, f"📉 TAPE: {sell_pct:.0f}% sells in last {total} trades → Selling pressure 🔴"

    return 0, ""


# ── Main Sniper Signal ────────────────────────────────────────────────────────
def generate_sniper_signal(asset="BTC") -> dict:
    from datetime import datetime, timezone
    score    = 0
    triggers = []
    reasons  = []

    # Session-aware threshold
    hour = datetime.now(timezone.utc).hour
    # London open (06:00-09:00 UTC) — volatile, require stronger signal
    if 6 <= hour < 9:
        min_score = 3
        reasons.append("⚠️ London open session — higher threshold (3+)")
    # NY open (13:00-16:00 UTC) — also volatile
    elif 13 <= hour < 16:
        min_score = 3
        reasons.append("⚠️ NY open session — higher threshold (3+)")
    # Asian session + off hours — normal sensitivity
    else:
        min_score = 1

    wall_s, wall_d = detect_order_book_wall(asset)
    if wall_s != 0:
        score += wall_s
        triggers.append(wall_d)

    liq_s, liq_d = detect_liquidation_cascade(asset)
    if liq_s != 0:
        score += liq_s
        triggers.append(liq_d)

    rn_s, rn_d = detect_round_number(asset)
    if rn_s != 0:
        score += rn_s
        triggers.append(rn_d)

    tape_s, tape_d = detect_tape_momentum(asset)
    if tape_s != 0:
        score += tape_s
        reasons.append(tape_d)

    max_score  = 7
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)
    confidence = max(0, min(100, confidence))

    # Session-aware threshold
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour < 9 or 13 <= hour < 16:
        # London/NY open — require stronger signal
        min_score = 3
        reasons.append(f"⚠️ Volatile session (hour {hour} UTC) — threshold +{min_score}")
    else:
        min_score = 2

    if score >= min_score:
        direction, label = "up",   "🟢 SNIPE UP"
    elif score <= -min_score:
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
        f"📈 Signal : {sig['label']}",
        f"🎯 Score  : {sig['score']}/7",
    ]
    if sig["triggers"]:
        lines.append("🔫 *Triggers:*")
        for t in sig["triggers"]:
            lines.append(f"  {t}")
    if sig["reasons"]:
        for r in sig["reasons"]:
            lines.append(f"  • {r}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{'🔫 SNIPE FIRING!' if sig['tradeable'] else '👁 Watching...'}")
    return "\n".join(lines)
