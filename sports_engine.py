"""
sports_engine.py — AI Sports Betting Engine
Scans Myriad Markets for sports markets and picks highest probability bets
"""

import requests

MYRIAD_API = "https://api-v2.myriadprotocol.com"

SPORTS_KEYWORDS = [
    "football", "soccer", "basketball", "nba", "nfl", "premier league",
    "champions league", "la liga", "bundesliga", "serie a", "ligue 1",
    "match", "game", "win", "score", "goal", "playoffs", "finals",
    "tournament", "world cup", "euro", "copa"
]


def get_sports_markets(network_id=56, limit=50):
    """Fetch all open markets and filter for sports."""
    try:
        resp = requests.get(
            f"{MYRIAD_API}/markets",
            params={
                "state": "open",
                "network_id": network_id,
                "sort": "volume",
                "order": "desc",
                "limit": limit
            },
            timeout=10
        )
        resp.raise_for_status()
        markets = resp.json().get("data", [])

        sports = []
        for m in markets:
            title = m.get("title", "").lower()
            topics = [t.lower() for t in m.get("topics", [])]
            is_sport = any(kw in title for kw in SPORTS_KEYWORDS) or \
                      any(kw in " ".join(topics) for kw in SPORTS_KEYWORDS)
            if is_sport:
                sports.append(m)

        return sports
    except Exception as e:
        print(f"Sports market fetch error: {e}")
        return []


def score_market(market: dict) -> dict:
    """
    Score a sports market by betting value.
    Returns scored market with best outcome to bet on.
    """
    outcomes = market.get("outcomes", [])
    if len(outcomes) < 2:
        return None

    liquidity = market.get("liquidity", 0)
    volume    = market.get("volume", 0)
    volume24h = market.get("volume24h", 0)

    best_outcome = None
    best_score   = -1

    for o in outcomes:
        price = o.get("price", 0)
        if price <= 0 or price >= 1:
            continue

        # Value scoring:
        # - Prefer outcomes with 55-75% probability (good value, not favorite)
        # - High volume = more reliable price discovery
        # - High liquidity = less slippage

        prob = price * 100

        # Skip extreme favorites and longshots
        if prob < 45 or prob > 78:
            continue

        # Score: closer to 65% = better value
        prob_score    = 1 - abs(prob - 65) / 65
        liquidity_score = min(liquidity / 10000, 1.0)
        volume_score  = min(volume24h / 5000, 1.0)

        total_score = (prob_score * 0.5) + (liquidity_score * 0.3) + (volume_score * 0.2)

        if total_score > best_score:
            best_score   = total_score
            best_outcome = o

    if not best_outcome:
        return None

    confidence = round(best_score * 100, 1)

    return {
        "market_id":    market["id"],
        "network_id":   market["networkId"],
        "market_title": market["title"],
        "outcome_id":   best_outcome["id"],
        "outcome_title": best_outcome["title"],
        "price":        best_outcome["price"],
        "implied_prob": f"{round(best_outcome['price'] * 100, 1)}%",
        "liquidity":    liquidity,
        "volume_24h":   volume24h,
        "confidence":   confidence,
        "expires_at":   market.get("expiresAt", ""),
    }


def find_best_sports_bet(min_confidence=60.0) -> dict:
    """
    Find the single best sports bet available right now.
    Returns the highest confidence scored market.
    """
    markets = get_sports_markets()
    if not markets:
        return None

    scored = []
    for m in markets:
        result = score_market(m)
        if result and result["confidence"] >= min_confidence:
            scored.append(result)

    if not scored:
        return None

    # Return highest confidence pick
    return sorted(scored, key=lambda x: x["confidence"], reverse=True)[0]


def format_sports_pick(pick: dict, amount: float) -> str:
    pot_payout = round(amount / pick["price"], 2)
    pot_profit = round(pot_payout - amount, 2)

    return (
        f"⚽ *AI Sports Pick*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Market    : {pick['market_title'][:50]}\n"
        f"Pick      : *{pick['outcome_title']}*\n"
        f"Odds      : {pick['implied_prob']}\n"
        f"Confidence: {pick['confidence']}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Stake     : ${amount:.2f} USD1\n"
        f"Potential : ~${pot_payout:.2f} USD1\n"
        f"Profit    : ~${pot_profit:.2f} USD1\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tap ✅ *Confirm* to place this bet\n"
        f"Tap ❌ *Skip* to pass"
    )
