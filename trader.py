"""
trader.py — On-chain trading on Myriad Markets (BSC)
Signs and sends transactions using user's private key
"""

import requests
import json
import os
from eth_account import Account
from eth_account.messages import encode_defunct

BSC_RPCS = [
    "https://rpc.ankr.com/bsc",
    "https://bsc-rpc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://bsc.meowrpc.com",
]
BSC_RPC = BSC_RPCS[0]
USD1_ADDRESS         = "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
MYRIAD_CONTRACT      = "0x39E66eE6b2ddaf4DEfDEd3038E0162180dbeF340"
MYRIAD_API           = "https://api-v2.myriadprotocol.com"
CHAIN_ID             = 56  # BSC Mainnet

# USD1 approve ABI
APPROVE_ABI = "0x095ea7b3"  # approve(address,uint256)

# Myriad buy ABI
BUY_ABI = "0x8a4e5e9c"  # buy(uint256,uint256,uint256,uint256)


def rpc_call(method, params):
    for rpc in BSC_RPCS:
        try:
            resp = requests.post(rpc, json={
                "jsonrpc": "2.0", "method": method,
                "params": params, "id": 1
            }, timeout=15)
            result = resp.json().get("result")
            if result is not None:
                return result
        except Exception as e:
            print(f"RPC {rpc} failed: {e}")
            continue
    raise Exception("All BSC RPC endpoints failed")


def get_nonce(address: str) -> int:
    result = rpc_call("eth_getTransactionCount", [address, "latest"])
    return int(result, 16)


def get_gas_price() -> int:
    result = rpc_call("eth_gasPrice", [])
    return int(result, 16)


def pad32(value: int) -> str:
    return hex(value)[2:].zfill(64)


def build_approve_data(spender: str, amount: int) -> str:
    """Build USD1 approve() calldata."""
    spender_padded = spender[2:].lower().zfill(64)
    amount_padded  = pad32(amount)
    return APPROVE_ABI + spender_padded + amount_padded


def sign_and_send(private_key: str, to: str, data: str, value: int = 0) -> str:
    """Sign a transaction and broadcast it."""
    account  = Account.from_key(private_key)
    address  = account.address
    nonce    = get_nonce(address)
    gas_price = get_gas_price()

    tx = {
        "nonce":    nonce,
        "gasPrice": gas_price,
        "gas":      200000,
        "to":       to,
        "value":    value,
        "data":     data,
        "chainId":  CHAIN_ID
    }

    signed = account.sign_transaction(tx)
    raw_tx = signed.rawTransaction.hex()
    if not raw_tx.startswith("0x"):
        raw_tx = "0x" + raw_tx

    tx_hash = rpc_call("eth_sendRawTransaction", [raw_tx])
    return tx_hash


def get_btc_market_and_outcome(direction: str) -> dict:
    """Get market ID and outcome ID from Myriad API."""
    resp = requests.get(
        f"{MYRIAD_API}/markets",
        params={"keyword": "bitcoin", "state": "open",
                "sort": "volume", "order": "desc",
                "network_id": 56, "limit": 20},
        timeout=10
    )
    resp.raise_for_status()
    markets = resp.json().get("data", [])

    for m in markets:
        outcomes = m.get("outcomes", [])
        titles   = [o["title"].lower() for o in outcomes]

        up_kw   = ["up", "higher", "more green"]
        down_kw = ["down", "lower", "more red"]

        has_up   = any(any(k in t for k in up_kw) for t in titles)
        has_down = any(any(k in t for k in down_kw) for t in titles)

        if has_up and has_down:
            for o in outcomes:
                t = o["title"].lower()
                if direction == "up" and any(k in t for k in up_kw):
                    return {
                        "market_id":  m["id"],
                        "network_id": m["networkId"],
                        "outcome_id": o["id"],
                        "title":      m["title"],
                        "outcome":    o["title"],
                        "price":      o["price"]
                    }
                if direction == "down" and any(k in t for k in down_kw):
                    return {
                        "market_id":  m["id"],
                        "network_id": m["networkId"],
                        "outcome_id": o["id"],
                        "title":      m["title"],
                        "outcome":    o["title"],
                        "price":      o["price"]
                    }
    raise Exception("No suitable BTC market found")


def get_quote(market_id: int, network_id: int, outcome_id: int, amount: float) -> dict:
    """Get trade quote and calldata from Myriad API."""
    resp = requests.post(
        f"{MYRIAD_API}/markets/quote",
        json={
            "market_id":  market_id,
            "network_id": network_id,
            "outcome_id": outcome_id,
            "action":     "buy",
            "value":      amount,
            "slippage":   0.01
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def place_trade(private_key: str, direction: str, amount_usd: float) -> dict:
    """
    Full trade flow:
    1. Get market + quote from Myriad API
    2. Approve USD1 spending
    3. Execute buy via Myriad contract
    Returns tx details
    """
    account = Account.from_key(private_key)
    address = account.address

    # Step 1 — Get market and quote
    market = get_btc_market_and_outcome(direction)
    quote  = get_quote(
        market["market_id"], market["network_id"],
        market["outcome_id"], amount_usd
    )

    shares   = round(quote.get("shares", 0), 4)
    calldata = quote.get("calldata")

    if not calldata:
        raise Exception("No calldata returned from Myriad API")

    # Step 2 — Approve USD1
    amount_wei    = int(amount_usd * 10**18)
    approve_data  = build_approve_data(MYRIAD_CONTRACT, amount_wei)
    approve_tx    = sign_and_send(private_key, USD1_ADDRESS, approve_data)

    if not approve_tx:
        raise Exception("Approval transaction failed")

    # Step 3 — Execute trade using Myriad calldata
    buy_tx = sign_and_send(private_key, MYRIAD_CONTRACT, calldata)

    if not buy_tx:
        raise Exception("Buy transaction failed")

    return {
        "direction":  direction,
        "amount":     amount_usd,
        "shares":     shares,
        "payout":     round(shares * 1.0, 2),
        "approve_tx": approve_tx,
        "buy_tx":     buy_tx,
        "market":     market["title"][:50],
        "outcome":    market["outcome"]
    }


def get_claimable_positions(wallet_address: str) -> list:
    """Get all claimable winning positions for a wallet."""
    try:
        resp = requests.get(
            f"{MYRIAD_API}/users/{wallet_address}/portfolio",
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [p for p in data if p.get("winningsToClaim") and not p.get("winningsClaimed")]
    except Exception as e:
        print(f"Portfolio fetch error: {e}")
        return []


def claim_winnings(private_key: str, market_id: int, network_id: int, outcome_id: int) -> dict:
    """Claim winnings for a resolved market."""
    # Get calldata from Myriad API
    resp = requests.post(
        f"{MYRIAD_API}/markets/claim",
        json={
            "market_id":  market_id,
            "network_id": network_id,
            "outcome_id": outcome_id
        },
        timeout=10
    )
    resp.raise_for_status()
    calldata = resp.json().get("calldata")

    if not calldata:
        raise Exception("No calldata returned for claim")

    tx_hash = sign_and_send(private_key, MYRIAD_CONTRACT, calldata)
    return {"tx_hash": tx_hash, "market_id": market_id}

def build_transfer_data(to: str, amount: int) -> str:
    """Build ERC20 transfer() calldata."""
    TRANSFER_ABI = "0xa9059cbb"
    to_padded     = to[2:].lower().zfill(64)
    amount_padded = pad32(amount)
    return TRANSFER_ABI + to_padded + amount_padded
