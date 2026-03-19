"""
trader.py — Myriad Markets trader using official Myriad CLI
Replaces custom RPC logic with myriad CLI for reliability
"""

import os
import json
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

MYRIAD_API  = "https://api-v2.myriadprotocol.com"
USD1_ADDRESS = "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
RPC_URL     = "https://bsc-rpc.publicnode.com"


def run_cli(args: list, private_key: str) -> dict:
    """Run myriad CLI command and return JSON output."""
    cmd = [
        "myriad",
        "--json",
        "--rpc-url", RPC_URL,
        "--private-key", private_key,
    ] + args

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise Exception(f"CLI error: {result.stderr.strip() or result.stdout.strip()}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # CLI returned plain text — still success
        return {"output": result.stdout.strip()}


def rpc_call(method: str, params: list):
    """Direct RPC call for read-only operations."""
    resp = requests.post(RPC_URL, json={
        "jsonrpc": "2.0", "method": method,
        "params": params, "id": 1
    }, timeout=15)
    return resp.json().get("result")


def get_open_market(asset: str = "bitcoin") -> dict:
    """Find the most current open candle market for given asset."""
    # Try with "candles" keyword first
    # Map asset shorthand to full name
    asset_name = {"bitcoin": "bitcoin", "btc": "bitcoin", "eth": "ethereum", "ethereum": "ethereum"}.get(asset.lower(), asset)
    for keyword in [f"{asset_name} candles", asset_name]:
        resp = requests.get(
            f"{MYRIAD_API}/markets",
            params={
                "keyword": keyword,
                "state": "open",
                "network_id": 56,
                "sort": "volume",
                "order": "desc",
                "limit": 20
            },
            timeout=10
        )
        resp.raise_for_status()
        markets = resp.json().get("data", [])

        for m in markets:
            title    = m.get("title", "").lower()
            outcomes = m.get("outcomes", [])
            # Must be a candle market with More Green/More Red
            has_green = any("green" in o.get("title","").lower() for o in outcomes)
            has_red   = any("red" in o.get("title","").lower() for o in outcomes)
            if has_green and has_red:
                return m

    raise Exception(f"No open {asset} candle market found")


def place_trade(private_key: str, direction: str,
                amount_usd: float, asset: str = "bitcoin") -> dict:
    """Place a trade using Myriad CLI."""

    # Get current open market
    market = get_open_market(asset)
    market_id  = market["id"]
    network_id = market["networkId"]
    outcomes   = market["outcomes"]

    # Map direction to outcome
    # More Green = UP = outcome 0
    # More Red   = DOWN = outcome 1
    if direction.lower() == "up":
        outcome = next((o for o in outcomes if "green" in o["title"].lower()), outcomes[0])
    else:
        outcome = next((o for o in outcomes if "red" in o["title"].lower()), outcomes[1])

    outcome_id = outcome["id"]

    # Execute trade via CLI
    result = run_cli([
        "trade", "buy",
        "--market-id",  str(market_id),
        "--network-id", str(network_id),
        "--outcome-id", str(outcome_id),
        "--value",      str(amount_usd),
        "--slippage",   "0.05",
    ], private_key)

    # Extract execution details
    execution = result.get("execution", {})
    quote     = result.get("quote", {})

    tx_hash = execution.get("txHash", "pending")
    shares  = quote.get("shares", 0)
    payout  = round(shares, 2)

    return {
        "direction":  direction,
        "amount":     amount_usd,
        "shares":     shares,
        "payout":     payout,
        "approve_tx": tx_hash,
        "buy_tx":     tx_hash,
        "market":     market["title"],
        "market_id":  market_id,
        "network_id": network_id,
        "outcome":    outcome["title"],
        "outcome_id": outcome_id,
        "status":     execution.get("status", 0),
    }


def get_claimable_positions(wallet_address: str) -> list:
    """Get claimable positions for wallet."""
    try:
        resp = requests.get(
            f"{MYRIAD_API}/users/{wallet_address}/portfolio",
            params={"network_id": 56, "page_size": 100},
            timeout=10
        )
        resp.raise_for_status()
        positions = resp.json().get("data", [])

        claimable = []
        for p in positions:
            if p.get("winningsToClaim") and not p.get("winningsClaimed"):
                shares = p.get("shares", 0)
                price  = p.get("price", 1)
                value  = round(shares * 1.0, 2)  # winning shares = $1 each
                profit = round(value - (shares * price), 2)
                claimable.append({
                    "marketId":     p["marketId"],
                    "networkId":    p.get("networkId", 56),
                    "outcomeId":    p["outcomeId"],
                    "marketTitle":  p.get("marketTitle", ""),
                    "outcomeTitle": p.get("outcomeTitle", ""),
                    "shares":       shares,
                    "value":        value,
                    "profit":       profit,
                    "roi":          profit / (shares * price) if shares * price > 0 else 0,
                })
        return claimable
    except Exception as e:
        print(f"Portfolio fetch error: {e}")
        return []


def claim_winnings(private_key: str, market_id: int,
                   network_id: int, outcome_id: int) -> dict:
    """Claim winnings using Myriad CLI."""
    result = run_cli([
        "claim", "winnings",
        "--market-id",  str(market_id),
        "--network-id", str(network_id),
        "--outcome-id", str(outcome_id),
    ], private_key)

    execution = result.get("execution", {})
    return {
        "tx_hash": execution.get("txHash", ""),
        "status":  execution.get("status", 0),
    }


def claim_all_winnings(private_key: str, wallet_address: str) -> dict:
    """Claim all claimable positions at once."""
    result = run_cli([
        "claim", "all",
        "--network-id", "56",
        "--wallet", wallet_address,
    ], private_key)
    return result


def build_transfer_data(to: str, amount: int) -> str:
    """Build ERC20 transfer() calldata."""
    TRANSFER_ABI = "0xa9059cbb"
    to_padded     = to[2:].lower().zfill(64)
    amount_padded = hex(amount)[2:].zfill(64)
    return TRANSFER_ABI + to_padded + amount_padded


def sign_and_send(private_key: str, to: str, data: str) -> str:
    """Send a raw transaction via CLI wallet."""
    from eth_account import Account
    import requests as req

    account  = Account.from_key(private_key)
    nonce    = rpc_call("eth_getTransactionCount", [account.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])

    tx = {
        "to":       to,
        "data":     data,
        "nonce":    int(nonce, 16),
        "gas":      100000,
        "gasPrice": int(gas_price, 16),
        "chainId":  56,
        "value":    0,
    }

    signed = Account.sign_transaction(tx, private_key)
    raw    = signed.raw_transaction.hex()
    if not raw.startswith("0x"):
        raw = "0x" + raw

    resp = req.post(RPC_URL, json={
        "jsonrpc": "2.0", "method": "eth_sendRawTransaction",
        "params": [raw], "id": 1
    }, timeout=20)
    return resp.json().get("result", "")
