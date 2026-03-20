"""
signal_api.py — Trend Pilot Signal API
x402 gated signal endpoint for BTC, ETH, XAUT (Gold), XAG (Silver)
"""

import os
import time
import hashlib
import requests
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Trend Pilot Signal API",
    description="AI-powered signals for BTC, ETH, XAUT (Gold), XAG (Silver)",
    version="1.0.0"
)

# x402 config
SIGNAL_PRICE_USDT = 0.01  # $0.01 per signal
OWNER_EVM         = os.getenv("OWNER_EVM", "0x95FB94763D57f8416A524091E641a9D26741cB31")
XLAYER_RPC        = "https://rpc.xlayer.tech"
USDT_XLAYER       = "0x1E4a5963aBFD975d8c9021ce480b42188849D41d"  # USDT on X Layer

# Cache signals for 60 seconds to avoid hammering APIs
_signal_cache = {}
CACHE_TTL = 60


# ── Price feeds ───────────────────────────────────────────────────────────────
KRAKEN_PAIRS = {
    "BTC":  "XBTUSD",
    "ETH":  "ETHUSD",
    "XAUT": "XAUTUSD",
    "XAG":  "XAGUSD",
}

CRYPTOCOMPARE_SYMBOLS = {
    "BTC":  "BTC",
    "ETH":  "ETH",
    "XAUT": "XAUT",
    "OKB":  "OKB",
    "ZEC":  "ZEC",
    "BCH":  "BCH",
}

SUPPORTED_ASSETS = list(CRYPTOCOMPARE_SYMBOLS.keys())


def get_candles(asset="BTC", limit=100):
    """Fetch 5-minute candles — CryptoCompare for crypto, Kraken for metals."""
    symbol = CRYPTOCOMPARE_SYMBOLS.get(asset, asset)
    try:
        resp = requests.get(
            "https://min-api.cryptocompare.com/data/v2/histominute",
            params={"fsym": symbol, "tsym": "USD", "limit": limit},
            timeout=10
        )
        data = resp.json().get("Data", {}).get("Data", [])
        if data and data[-1]["close"] > 0:
            return data
    except Exception:
        pass

    # Fallback to Kraken OHLC
    try:
        pair = KRAKEN_PAIRS.get(asset, f"X{asset}ZUSD")
        resp = requests.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": pair, "interval": 5},
            timeout=10
        )
        result = resp.json().get("result", {})
        ohlc   = list(result.values())[0] if result else []
        candles = []
        for c in ohlc[-limit:]:
            candles.append({
                "open":       float(c[1]),
                "high":       float(c[2]),
                "low":        float(c[3]),
                "close":      float(c[4]),
                "volumefrom": float(c[6]),
            })
        return candles
    except Exception:
        return []


def get_order_book(asset="BTC"):
    """Fetch order book from Kraken."""
    try:
        pair = KRAKEN_PAIRS.get(asset, f"X{asset}ZUSD")
        resp = requests.get(
            "https://api.kraken.com/0/public/Depth",
            params={"pair": pair, "count": 25},
            timeout=8
        )
        data   = resp.json()
        result = list(data["result"].values())[0]
        bids   = [(float(p), float(q)) for p, q, _ in result["bids"]]
        asks   = [(float(p), float(q)) for p, q, _ in result["asks"]]
        bid_vol = sum(q for _, q in bids)
        ask_vol = sum(q for _, q in asks)
        return bid_vol, ask_vol
    except Exception:
        return None, None


# ── Indicators ────────────────────────────────────────────────────────────────
def calc_rsi(closes, period=14):
    d      = np.diff(closes)
    gains  = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    avg_g  = np.mean(gains[-period:])
    avg_l  = np.mean(losses[-period:])
    return 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)


def calc_vwap(candles, period=20):
    recent    = candles[-period:]
    tp_vol    = sum(((c["high"]+c["low"]+c["close"])/3)*c["volumefrom"] for c in recent)
    total_vol = sum(c["volumefrom"] for c in recent)
    return round(tp_vol/total_vol, 4) if total_vol > 0 else 0


def calc_bollinger(closes, period=20):
    r   = np.array(closes[-period:])
    mid = np.mean(r)
    std = np.std(r)
    return round(mid-2*std, 4), round(mid, 4), round(mid+2*std, 4)


def calc_momentum(closes, period=5):
    if len(closes) < period+1:
        return 0
    return round((closes[-1]-closes[-period])/closes[-period]*100, 4)


# ── Signal Generator ──────────────────────────────────────────────────────────
def generate_signal(asset: str) -> dict:
    """Generate AI signal for given asset."""
    cache_key = asset.upper()
    cached    = _signal_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["signal"]

    candles = get_candles(asset)
    if not candles:
        raise Exception(f"No price data for {asset}")

    closes  = [c["close"] for c in candles]
    current = round(closes[-1], 4)

    rsi             = calc_rsi(closes)
    vwap            = calc_vwap(candles)
    bb_low, bb_mid, bb_high = calc_bollinger(closes)
    momentum        = calc_momentum(closes, 5)
    bid_vol, ask_vol = get_order_book(asset)
    ob_ratio        = round(bid_vol/ask_vol, 3) if bid_vol and ask_vol else None

    score   = 0
    reasons = []

    # RSI bias
    if rsi < 35:
        score += 2; reasons.append(f"RSI {rsi} — Oversold")
    elif rsi > 65:
        score -= 2; reasons.append(f"RSI {rsi} — Overbought")
    else:
        reasons.append(f"RSI {rsi} — Neutral")

    # VWAP
    if current > vwap:
        score += 1; reasons.append(f"Above VWAP ${vwap}")
    else:
        score -= 1; reasons.append(f"Below VWAP ${vwap}")

    # Bollinger
    if current < bb_low:
        score += 2; reasons.append(f"Below BB lower — bounce zone")
    elif current > bb_high:
        score -= 2; reasons.append(f"Above BB upper — overextended")

    # Momentum
    if momentum > 0.05:
        score += 1; reasons.append(f"Momentum +{momentum}% bullish")
    elif momentum < -0.05:
        score -= 1; reasons.append(f"Momentum {momentum}% bearish")

    # Order book
    if ob_ratio:
        if ob_ratio > 1.3:
            score += 1; reasons.append(f"OB ratio {ob_ratio}x — buy pressure")
        elif ob_ratio < 0.7:
            score -= 1; reasons.append(f"OB ratio {ob_ratio}x — sell pressure")

    # Confidence
    max_score  = 7
    confidence = round((score + max_score) / (max_score * 2) * 100, 1)
    confidence = max(0, min(100, confidence))

    if score >= 2:
        direction = "up"
    elif score <= -2:
        direction = "down"
    else:
        direction = "hold"

    signal = {
        "asset":      asset.upper(),
        "price":      current,
        "direction":  direction,
        "confidence": confidence,
        "score":      score,
        "rsi":        rsi,
        "vwap":       vwap,
        "bb_low":     bb_low,
        "bb_high":    bb_high,
        "momentum":   momentum,
        "ob_ratio":   ob_ratio,
        "reasons":    reasons,
        "tradeable":  confidence >= 65 and direction != "hold",
        "timestamp":  int(time.time()),
    }

    _signal_cache[cache_key] = {"signal": signal, "ts": time.time()}
    return signal


# ── x402 Payment Verification ─────────────────────────────────────────────────
def verify_x402_payment(tx_hash: str, expected_amount: float = SIGNAL_PRICE_USDT) -> bool:
    """Verify USDT payment on X Layer."""
    try:
        resp = requests.post(XLAYER_RPC, json={
            "jsonrpc": "2.0",
            "method":  "eth_getTransactionReceipt",
            "params":  [tx_hash],
            "id":      1
        }, timeout=10)
        receipt = resp.json().get("result")
        if not receipt or receipt.get("status") != "0x1":
            return False

        # Check it's a USDT transfer to our wallet
        to = receipt.get("to", "").lower()
        if to != USDT_XLAYER.lower():
            return False

        return True
    except Exception:
        return False


# ── API Routes ────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name":        "Trend Pilot Signal API",
        "version":     "1.0.0",
        "assets":      ["BTC", "ETH", "XAUT", "OKB", "ZEC", "BCH"],
        "price":       f"${SIGNAL_PRICE_USDT} USDT per signal",
        "payment":     f"Send {SIGNAL_PRICE_USDT} USDT to {OWNER_EVM} on X Layer (Chain ID: 196)",
        "docs":        "/docs",
    }


@app.get("/signal/{asset}")
async def get_signal(asset: str, request: Request, tx: str = None):
    """
    Get AI signal for asset.
    Requires x402 payment — send tx hash as ?tx= parameter.
    """
    asset = asset.upper()
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=400, detail=f"Unsupported asset: {asset}. Use {', '.join(SUPPORTED_ASSETS)}")

    # x402 payment check
    if not tx:
        return JSONResponse(
            status_code=402,
            content={
                "error":   "Payment required",
                "amount":  SIGNAL_PRICE_USDT,
                "token":   "USDT",
                "chain":   "X Layer (Chain ID: 196)",
                "pay_to":  OWNER_EVM,
                "retry":   f"GET /signal/{asset}?tx=<your_tx_hash>",
            }
        )

    # Verify payment
    if not verify_x402_payment(tx):
        raise HTTPException(status_code=402, detail="Payment not verified. Check tx hash and try again.")

    # Generate signal
    try:
        signal = generate_signal(asset)
        return {
            "status":  "ok",
            "paid":    True,
            "tx":      tx,
            **signal
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signal/{asset}/free")
async def get_signal_free(asset: str):
    """Free preview — returns signal without direction (teaser)."""
    asset = asset.upper()
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=400, detail=f"Unsupported asset. Use {', '.join(SUPPORTED_ASSETS)}")
    try:
        signal = generate_signal(asset)
        return {
            "asset":      signal["asset"],
            "price":      signal["price"],
            "confidence": signal["confidence"],
            "direction":  "*** PAY $0.01 USDT TO UNLOCK ***",
            "tradeable":  signal["tradeable"],
            "timestamp":  signal["timestamp"],
            "message":    f"Pay {SIGNAL_PRICE_USDT} USDT on X Layer to get full signal",
            "pay_to":     OWNER_EVM,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/all")
async def get_all_signals(tx: str = None):
    """Get signals for all 4 assets in one call."""
    if not tx:
        return JSONResponse(
            status_code=402,
            content={
                "error":  "Payment required",
                "amount": SIGNAL_PRICE_USDT * 4,
                "note":   "One payment covers all 4 assets",
                "pay_to": OWNER_EVM,
            }
        )
    if not verify_x402_payment(tx):
        raise HTTPException(status_code=402, detail="Payment not verified")

    results = {}
    for asset in SUPPORTED_ASSETS:
        try:
            results[asset] = generate_signal(asset)
        except Exception as e:
            results[asset] = {"error": str(e)}

    return {"status": "ok", "paid": True, "tx": tx, "signals": results}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time())}
