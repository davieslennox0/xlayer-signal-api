"""
wallet_manager.py — Per-user wallet generation and management
"""

from eth_account import Account
from web3 import Web3
import os

# Abstract chain RPC (fallback to BNB if needed)
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet.abs.xyz")

# USDC contract on Abstract chain
USDC_ADDRESS = os.getenv("USDC_ADDRESS", "0x84A71ccD554Cc1b02749b35d22F684CC8ec987e1")

USDC_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def generate_wallet() -> dict:
    """Generate a new ETH wallet. Returns address + private key."""
    account = Account.create()
    return {
        "address":     account.address,
        "private_key": account.key.hex()
    }


def get_usdc_balance(address: str) -> float:
    """Get USDC balance for a wallet address."""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=USDC_ABI
        )
        raw_balance = contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        decimals = contract.functions.decimals().call()
        return round(raw_balance / (10 ** decimals), 4)
    except Exception as e:
        print(f"Balance check error: {e}")
        return 0.0


def verify_tx_payment(tx_hash: str, expected_to: str, min_amount_usd: float = 5.0) -> dict:
    """
    Verify a USDC transaction on-chain.
    Returns: { valid: bool, amount: float, error: str }
    """
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))

        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)

        if not receipt or receipt["status"] != 1:
            return {"valid": False, "amount": 0, "error": "Transaction failed or not found"}

        # Check it went to USDC contract
        if tx["to"].lower() != USDC_ADDRESS.lower():
            return {"valid": False, "amount": 0, "error": "Not a USDC transaction"}

        # Decode transfer(address,uint256) call
        # Function selector: 0xa9059cbb
        input_data = tx["input"].hex() if isinstance(tx["input"], bytes) else tx["input"]

        if not input_data.startswith("0xa9059cbb"):
            return {"valid": False, "amount": 0, "error": "Not a USDC transfer"}

        # Decode recipient and amount from calldata
        recipient = "0x" + input_data[34:74]
        amount_raw = int(input_data[74:138], 16)
        amount_usdc = amount_raw / 1_000_000  # USDC has 6 decimals

        if recipient.lower() != expected_to.lower():
            return {
                "valid": False, "amount": amount_usdc,
                "error": f"Sent to wrong address. Expected {expected_to[:10]}..."
            }

        if amount_usdc < min_amount_usd:
            return {
                "valid": False, "amount": amount_usdc,
                "error": f"Amount too low: ${amount_usdc:.2f} (need ${min_amount_usd})"
            }

        return {"valid": True, "amount": amount_usdc, "error": None}

    except Exception as e:
        return {"valid": False, "amount": 0, "error": str(e)}
