"""
myriad_client.py — Myriad Markets API + CLI integration
"""

import requests
import subprocess
import json
import os

MYRIAD_API = "https://api-v2.myriadprotocol.com"
MYRIAD_KEY = os.getenv("MYRIAD_API_KEY", "")


def headers():
    return {"x-api-key": MYRIAD_KEY} if MYRIAD_KEY else {}


def get_btc_market():
    """Find most active open BTC UP/DOWN market."""
    resp = requests.get(
        f"{MYRIAD_API}/markets",
        params={"keyword": "bitcoin price", "state": "open",
                "sort": "volume", "order": "desc", "limit": 20},
        headers=headers(), timeout=10
    )
    resp.raise_for_status()
    markets = resp.json().get("data", [])

    for m in markets:
        titles = [o["title"].lower() for o in m.get("outcomes", [])]
        if any("up" in t or "higher" in t for t in titles) and \
           any("down" in t or "lower" in t for t in titles):
            return m

    # fallback — first result
    return markets[0] if markets else None


def get_market_odds(market: dict) -> dict:
    result = {
        "market_id": market["id"],
        "network_id": market["networkId"],
        "title": market["title"],
        "outcomes": {}
    }
    for o in market.get("outcomes", []):
        t = o["title"].lower()
        key = "up" if ("up" in t or "higher" in t or "yes" in t) else "down"
        result["outcomes"][key] = {
            "id": o["id"],
            "title": o["title"],
            "price": round(o["price"], 4),
            "implied_prob": f"{round(o['price'] * 100, 1)}%"
        }
    return result


def get_quote(market_id, network_id, outcome_id, value) -> dict:
    resp = requests.post(
        f"{MYRIAD_API}/markets/quote",
        json={
            "market_id": market_id,
            "network_id": network_id,
            "outcome_id": outcome_id,
            "action": "buy",
            "value": value,
            "slippage": 0.01
        },
        headers=headers(), timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def place_bet(market_id: int, outcome_id: int, value: float) -> dict:
    """Execute trade via Myriad CLI."""
    result = subprocess.run(
        ["myriad", "trade", "buy",
         "--market-id", str(market_id),
         "--outcome-id", str(outcome_id),
         "--value", str(value),
         "--json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Trade failed")
    return json.loads(result.stdout.strip())
