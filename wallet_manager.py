from dotenv import load_dotenv
load_dotenv()
"""
wallet_manager.py — BSC/USD1 wallet management with encryption
"""

import secrets
import hashlib
import requests
import os
from cryptography.fernet import Fernet

BSC_RPC = "https://rpc.ankr.com/bsc"
USD1_ADDRESS = "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
MASTER_KEY   = os.getenv("MASTER_KEY")


def get_cipher():
    return Fernet(MASTER_KEY.encode() if isinstance(MASTER_KEY, str) else MASTER_KEY)


def encrypt_key(private_key: str) -> str:
    return get_cipher().encrypt(private_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    return get_cipher().decrypt(encrypted_key.encode()).decode()


def generate_wallet() -> dict:
    """Generate a proper EVM wallet using eth_account."""
    from eth_account import Account
    private_key = "0x" + secrets.token_hex(32)
    account     = Account.from_key(private_key)
    address     = account.address
    return {
        "address":       address,
        "private_key":   private_key,
        "encrypted_key": encrypt_key(private_key)
    }


def get_usd1_balance(address: str) -> float:
    try:
        payload = {
            "jsonrpc": "2.0", "method": "eth_call",
            "params": [{
                "to":   USD1_ADDRESS,
                "data": "0x70a08231000000000000000000000000" + address[2:].lower().zfill(40)
            }, "latest"],
            "id": 1
        }
        resp   = requests.post(BSC_RPC, json=payload, timeout=10)
        result = resp.json().get("result", "0x0")
        return round(int(result, 16) / 10**18, 4)
    except Exception as e:
        print(f"Balance error: {e}")
        return 0.0


def verify_tx_payment(tx_hash: str, expected_to: str, min_amount_usd: float = 5.0) -> dict:
    try:
        payload = {
            "jsonrpc": "2.0", "method": "eth_getTransactionByHash",
            "params": [tx_hash], "id": 1
        }
        resp = requests.post(BSC_RPC, json=payload, timeout=10)
        tx   = resp.json().get("result")

        if not tx:
            return {"valid": False, "amount": 0, "error": "Transaction not found"}

        if tx.get("to", "").lower() != USD1_ADDRESS.lower():
            return {"valid": False, "amount": 0, "error": "Not a USD1 transaction"}

        input_data = tx.get("input", "")
        if not input_data.startswith("0xa9059cbb"):
            return {"valid": False, "amount": 0, "error": "Not a USD1 transfer"}

        recipient  = "0x" + input_data[34:74]
        amount_raw = int(input_data[74:138], 16)
        amount_usd = round(amount_raw / 10**18, 4)

        if recipient.lower() != expected_to.lower():
            return {"valid": False, "amount": amount_usd, "error": "Sent to wrong address"}

        if amount_usd < min_amount_usd:
            return {"valid": False, "amount": amount_usd,
                    "error": f"Amount too low: ${amount_usd:.2f} (need ${min_amount_usd})"}

        return {"valid": True, "amount": amount_usd, "error": None}

    except Exception as e:
        return {"valid": False, "amount": 0, "error": str(e)}
