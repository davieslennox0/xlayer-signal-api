"""
demo_agent.py — Autonomous Trading Agent
Pays for signals via x402, executes trades on X Layer DEX
"""

import os
import time
import requests
import json
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

SIGNAL_API    = "http://localhost:8000"
XLAYER_RPC    = "https://rpc.xlayer.tech"
OWNER_EVM     = os.getenv("OWNER_EVM")
MASTER_KEY    = os.getenv("MASTER_KEY")
SIGNAL_PRICE  = 0.01
USDT_XLAYER   = "0x779Ded0c9e1022225f8E0630b35a9b54bE713736"
CHAIN_ID      = 196

# Agent wallet — uses existing wallet
AGENT_KEY     = None  # Set after wallet_manager loads
AGENT_ADDRESS = "0xB0ec9D8E13d7d38206cc4F9022A7768A34d07c4C"


def rpc_call(method, params):
    resp = requests.post(XLAYER_RPC, json={
        "jsonrpc": "2.0", "method": method,
        "params": params, "id": 1
    }, timeout=10)
    return resp.json().get("result")


def get_usdt_balance(wallet):
    data = "0x70a08231000000000000000000000000" + wallet[2:].lower()
    raw  = rpc_call("eth_call", [{"to": USDT_XLAYER, "data": data}, "latest"])
    return int(raw, 16) / 10**6 if raw else 0


def pay_for_signal(private_key: str, amount_usdt: float = SIGNAL_PRICE) -> str:
    """Send USDT payment to Signal API owner on X Layer."""
    account   = Account.from_key(private_key)
    nonce     = int(rpc_call("eth_getTransactionCount", [account.address, "latest"]), 16)
    gas_price = int(rpc_call("eth_gasPrice", []), 16)

    # ERC20 transfer calldata — USDT0 uses 6 decimals
    amount_wei = int(amount_usdt * 10**6)
    to_padded  = OWNER_EVM[2:].lower().zfill(64)
    amt_padded = hex(amount_wei)[2:].zfill(64)
    data       = "0xa9059cbb" + to_padded + amt_padded

    tx = {
        "to":       USDT_XLAYER,
        "data":     data,
        "nonce":    nonce,
        "gas":      100000,
        "gasPrice": gas_price,
        "chainId":  CHAIN_ID,
        "value":    0,
    }

    signed = Account.sign_transaction(tx, private_key)
    raw    = signed.raw_transaction.hex()
    if not raw.startswith("0x"):
        raw = "0x" + raw

    result = rpc_call("eth_sendRawTransaction", [raw])
    return result


def get_signal_with_payment(private_key: str, asset: str) -> dict:
    """Pay for signal and retrieve it."""
    print(f"\n🔍 Requesting {asset} signal...")

    # Check free preview first
    free = requests.get(f"{SIGNAL_API}/signal/{asset}/free").json()
    print(f"   Price: ${free['price']} | Confidence: {free['confidence']}%")

    # Always pay — agent pays per request regardless of confidence

    # Pay for full signal
    print(f"   💳 Paying ${SIGNAL_PRICE} USDT via x402...")
    tx_hash = pay_for_signal(private_key, SIGNAL_PRICE)

    if not tx_hash:
        print(f"   ❌ Payment failed")
        return None

    print(f"   ✅ Payment tx: {tx_hash[:20]}...")

    # Wait for confirmation
    time.sleep(3)

    # Get full signal
    signal = requests.get(
        f"{SIGNAL_API}/signal/{asset}",
        params={"tx": tx_hash}
    ).json()

    return signal


def run_agent(private_key: str):
    """Main agent loop — runs every 5 minutes."""
    print("🤖 Trend Pilot Trading Agent Started")
    print(f"   Wallet: {AGENT_ADDRESS}")
    print(f"   Signal API: {SIGNAL_API}")
    print(f"   Assets: BTC, ETH, XAUT, OKB, ZEC, BCH")

    while True:
        print(f"\n{'='*50}")
        print(f"⏰ Scan at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

        # Check balance
        usdt_bal = get_usdt_balance(AGENT_ADDRESS)
        print(f"💰 USDT Balance: ${usdt_bal:.4f}")

        if usdt_bal < SIGNAL_PRICE:
            print("❌ Insufficient USDT for signal payment. Top up wallet.")
            time.sleep(300)
            continue

        # Scan all assets
        best_signal = None
        for asset in ["BTC", "ETH", "XAUT", "OKB", "ZEC", "BCH"]:
            try:
                # Check free preview — only pay for tradeable signals
                free = requests.get(
                    f"{SIGNAL_API}/signal/{asset}/free",
                    timeout=10
                ).json()

                price = free.get('price', 'N/A')
                conf  = free.get('confidence', 0)
                print(f"   {asset}: ${price} | {conf}% confidence")

                # Always pay for full signal — agent pays per request
                signal = get_signal_with_payment(private_key, asset)
                if signal:
                    if not best_signal or signal.get("confidence", 0) > best_signal.get("confidence", 0):
                        best_signal = signal

            except Exception as e:
                print(f"   {asset}: Error — {e}")

        # Act on best signal
        if best_signal:
            asset = best_signal.get("asset", "N/A"); direction = best_signal.get("direction", "hold"); print(f"\n🔫 BEST SIGNAL: {asset} {direction.upper()}")
            print(f"   Confidence: {best_signal.get("confidence", 0)}%")
            print(f"   Reasons: {', '.join(best_signal.get('reasons', [])[:3])}")
            print(f"   Action: Execute {best_signal.get("direction", "hold").upper()} trade on X Layer DEX")
            # Trade execution will be added once OKX DEX API is integrated
        else:
            print("\n⏸ No tradeable signals — waiting...")

        print(f"\n⏳ Next scan in 5 minutes...")
        time.sleep(300)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Load private key from env or prompt
    pk = os.getenv("AGENT_PRIVATE_KEY")
    if not pk:
        pk = input("Enter agent private key: ").strip()
    run_agent(pk)
