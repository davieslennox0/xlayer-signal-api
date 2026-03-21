"""
x402_payment.py — Gasless USDT payments via OKX x402 API
No OKB needed for gas — OKX sponsors the transaction
"""

import requests
import time
from eth_account import Account
from eth_account.messages import encode_defunct

X402_API    = "https://www.okx.com/api/v5/wallet/payment"
XLAYER_RPC  = "https://rpc.xlayer.tech"
USDT0       = "0x779Ded0c9e1022225f8E0630b35a9b54bE713736"
CHAIN_ID    = "196"


def get_payment_schemes():
    """Get supported payment schemes from OKX x402 API."""
    resp = requests.get(
        f"{X402_API}/schemes",
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    return resp.json()


def submit_payment(private_key: str, to: str, amount_usdt: float) -> dict:
    """
    Submit gasless USDT payment via OKX x402 API.
    OKX sponsors the gas — no OKB needed.
    """
    account    = Account.from_key(private_key)
    amount_raw = int(amount_usdt * 10**6)  # USDT0 has 6 decimals

    # Build transfer calldata
    to_padded  = to[2:].lower().zfill(64)
    amt_padded = hex(amount_raw)[2:].zfill(64)
    calldata   = "0xa9059cbb" + to_padded + amt_padded

    # Get nonce
    resp  = requests.post(XLAYER_RPC, json={
        "jsonrpc": "2.0", "method": "eth_getTransactionCount",
        "params": [account.address, "latest"], "id": 1
    }, timeout=10)
    nonce = int(resp.json().get("result", "0x0"), 16)

    # Build unsigned tx
    tx = {
        "from":     account.address,
        "to":       USDT0,
        "data":     calldata,
        "value":    "0x0",
        "nonce":    hex(nonce),
        "chainId":  CHAIN_ID,
    }

    # Sign the tx
    tx_to_sign = {
        "to":      USDT0,
        "data":    calldata,
        "value":   0,
        "nonce":   nonce,
        "gas":     100000,
        "gasPrice": 0,  # Gasless
        "chainId": int(CHAIN_ID),
    }

    signed    = Account.sign_transaction(tx_to_sign, private_key)
    raw_tx    = signed.raw_transaction.hex()
    if not raw_tx.startswith("0x"):
        raw_tx = "0x" + raw_tx

    # Submit to OKX x402 API for gasless relay
    payload = {
        "chainIndex": CHAIN_ID,
        "signedTx":   raw_tx,
        "from":       account.address,
        "to":         USDT0,
        "tokenAddress": USDT0,
        "amount":     str(amount_raw),
    }

    resp2 = requests.post(
        f"{X402_API}/submit-transaction",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )

    result = resp2.json()
    return result


def verify_payment(tx_hash: str) -> bool:
    """Verify payment was confirmed on X Layer."""
    for _ in range(10):
        resp = requests.post(XLAYER_RPC, json={
            "jsonrpc": "2.0", "method": "eth_getTransactionReceipt",
            "params": [tx_hash], "id": 1
        }, timeout=10)
        receipt = resp.json().get("result")
        if receipt:
            return receipt.get("status") == "0x1"
        time.sleep(3)
    return False


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test get schemes
    schemes = get_payment_schemes()
    print("Schemes:", schemes)
