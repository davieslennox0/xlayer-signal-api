import os
import json
import time
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
WALLET = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS"))
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CHAIN_ID = int(os.getenv("CHAIN_ID", 196))

# X Layer token addresses
USDT0  = Web3.to_checksum_address("0x779Ded0c9e1022225f8E0630b35a9b54bE713736")
WOKB   = Web3.to_checksum_address("0xe538905cf8410324e03A5A23C1c177a474D59b2b")
WETH   = Web3.to_checksum_address("0x5A77f1443D16ee5761d310e38b62f77f726bC71c")

# Uniswap V3 SwapRouter on X Layer
SWAP_ROUTER = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")

SWAP_ROUTER_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn",        "type": "address"},
                {"name": "tokenOut",       "type": "address"},
                {"name": "fee",            "type": "uint24"},
                {"name": "recipient",      "type": "address"},
                {"name": "deadline",       "type": "uint256"},
                {"name": "amountIn",       "type": "uint256"},
                {"name": "amountOutMinimum","type": "uint256"},
                {"name": "sqrtPriceLimitX96","type": "uint160"},
            ],
            "name": "params",
            "type": "tuple"
        }],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

ERC20_ABI = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],
     "name":"approve","outputs":[{"name":"","type":"bool"}],
     "type":"function","stateMutability":"nonpayable"},
    {"inputs":[{"name":"account","type":"address"}],
     "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
     "type":"function","stateMutability":"view"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],
     "name":"allowance","outputs":[{"name":"","type":"uint256"}],
     "type":"function","stateMutability":"view"}
]

ASSET_TO_TOKEN = {
    "BTC":  WOKB,   # proxy — no WBTC on X Layer yet, use WOKB
    "ETH":  WETH,
    "OKB":  WOKB,
}

def get_token_out(asset: str, direction: str) -> tuple:
    """Returns (token_in, token_out) based on direction."""
    token = ASSET_TO_TOKEN.get(asset, WOKB)
    if direction.upper() == "UP":
        return USDT0, token   # buy token with USDT0
    else:
        return token, USDT0   # sell token for USDT0

def approve_token(token_address: str, amount_wei: int) -> str | None:
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    allowance = token.functions.allowance(WALLET, SWAP_ROUTER).call()
    if allowance >= amount_wei:
        return None  # already approved

    nonce = w3.eth.get_transaction_count(WALLET)
    tx = token.functions.approve(SWAP_ROUTER, amount_wei).build_transaction({
        "from": WALLET,
        "nonce": nonce,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    print(f"Approved: {tx_hash.hex()}")
    return tx_hash.hex()

def execute_swap(asset: str, direction: str, amount_usdt: float) -> dict:
    token_in, token_out = get_token_out(asset, direction)

    # USDT0 has 6 decimals, tokens have 18
    if token_in == USDT0:
        amount_in_wei = int(amount_usdt * 1e6)
    else:
        # need to convert asset amount — use 18 decimals
        amount_in_wei = int(amount_usdt * 1e18)

    # Approve spend
    approve_token(token_in, amount_in_wei)

    router = w3.eth.contract(address=SWAP_ROUTER, abi=SWAP_ROUTER_ABI)
    deadline = int(time.time()) + 300  # 5 min

    params = {
        "tokenIn":           token_in,
        "tokenOut":          token_out,
        "fee":               3000,      # 0.3% pool
        "recipient":         WALLET,
        "deadline":          deadline,
        "amountIn":          amount_in_wei,
        "amountOutMinimum":  0,         # Risk Agent handles slippage
        "sqrtPriceLimitX96": 0,
    }

    nonce = w3.eth.get_transaction_count(WALLET)
    tx = router.functions.exactInputSingle(params).build_transaction({
        "from":     WALLET,
        "nonce":    nonce,
        "gas":      300000,
        "gasPrice": w3.eth.gas_price,
        "chainId":  CHAIN_ID,
        "value":    0,
    })
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    status = "success" if receipt["status"] == 1 else "failed"
    return {
        "status":     status,
        "tx_hash":    tx_hash.hex(),
        "asset":      asset,
        "direction":  direction,
        "amount_usdt": amount_usdt,
        "block":      receipt["blockNumber"],
        "gas_used":   receipt["gasUsed"],
        "explorer":   f"https://www.oklink.com/xlayer/tx/{tx_hash.hex()}"
    }

if __name__ == "__main__":
    print(f"Connected: {w3.is_connected()}")
    print(f"Wallet: {WALLET}")
    okb_balance = w3.eth.get_balance(WALLET) / 1e18
    print(f"OKB balance: {okb_balance:.6f}")

    usdt0 = w3.eth.contract(address=USDT0, abi=ERC20_ABI)
    usdt_bal = usdt0.functions.balanceOf(WALLET).call() / 1e6
    print(f"USDT0 balance: {usdt_bal:.4f}")
    print("Execution Agent ready — awaiting funded wallet to test swaps")
