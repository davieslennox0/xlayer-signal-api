import os
import time
import json
import logging
import requests
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("agents.log"),
        logging.StreamHandler()
    ]
)

w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
CHAIN_ID = int(os.getenv("CHAIN_ID", 196))
BROKER_URL = "http://localhost:8000"

USDT0 = Web3.to_checksum_address("0x779Ded0c9e1022225f8E0630b35a9b54bE713736")
BROKER_WALLET = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS"))

ERC20_ABI = [
    {"inputs":[{"name":"account","type":"address"}],
     "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
     "type":"function","stateMutability":"view"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],
     "name":"transfer","outputs":[{"name":"","type":"bool"}],
     "type":"function","stateMutability":"nonpayable"}
]

AGENTS = [
    {
        "name":    "Alice",
        "address": Web3.to_checksum_address(os.getenv("AGENT_ALICE_ADDRESS")),
        "key":     os.getenv("AGENT_ALICE_KEY"),
        "asset":   "BTC",
        "interval": 300,  # scans every 5 min
    },
    {
        "name":    "Bob",
        "address": Web3.to_checksum_address(os.getenv("AGENT_BOB_ADDRESS")),
        "key":     os.getenv("AGENT_BOB_KEY"),
        "asset":   "ETH",
        "interval": 420,  # scans every 7 min
    },
    {
        "name":    "Charlie",
        "address": Web3.to_checksum_address(os.getenv("AGENT_CHARLIE_ADDRESS")),
        "key":     os.getenv("AGENT_CHARLIE_KEY"),
        "asset":   "SOL",
        "interval": 360,  # scans every 6 min
    },
]

def get_usdt0_balance(address: str) -> float:
    usdt0 = w3.eth.contract(address=USDT0, abi=ERC20_ABI)
    bal = usdt0.functions.balanceOf(Web3.to_checksum_address(address)).call()
    return bal / 1e6

def pay_broker(agent: dict, amount_usdt: float) -> str | None:
    """Agent pays x402 fee to broker wallet."""
    usdt0 = w3.eth.contract(address=USDT0, abi=ERC20_ABI)
    amount_wei = int(amount_usdt * 1e6)

    bal = get_usdt0_balance(agent["address"])
    if bal < amount_usdt:
        return None

    nonce = w3.eth.get_transaction_count(
        Web3.to_checksum_address(agent["address"])
    )
    tx = usdt0.functions.transfer(
        BROKER_WALLET, amount_wei
    ).build_transaction({
        "from":     Web3.to_checksum_address(agent["address"]),
        "nonce":    nonce,
        "gas":      100000,
        "gasPrice": w3.eth.gas_price,
        "chainId":  CHAIN_ID,
    })
    signed = w3.eth.account.sign_transaction(tx, agent["key"])
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] == 1:
        return tx_hash.hex()
    return None

def agent_cycle(agent: dict):
    log = logging.getLogger(agent["name"])
    asset = agent["asset"]

    # Check balance
    bal = get_usdt0_balance(agent["address"])
    log.info(f"Balance: ${bal:.4f} USDT0 | Scanning {asset}...")

    if bal < 0.02:
        log.info(f"Insufficient balance for full broker call — skipping")
        return

    # Pay x402 fee to broker
    log.info(f"Paying $0.02 x402 fee to broker...")
    tx_hash = pay_broker(agent, 0.02)
    if not tx_hash:
        log.info(f"Payment failed — skipping")
        return

    log.info(f"Payment tx: {tx_hash}")

    # Call AlphaLoop broker
    try:
        res = requests.post(f"{BROKER_URL}/broker", json={
            "asset":    asset,
            "agent_id": agent["name"].lower(),
            "tx_hash":  tx_hash
        }, timeout=60)
        result = res.json()
        status = result.get("status", "unknown")
        log.info(f"Broker response: {status}")

        if status == "success":
            log.info(f"Trade executed: {result.get('explorer')}")
        elif status == "waiting":
            log.info(f"Agent waiting: {result.get('reason')}")
        else:
            log.info(f"Rejected: {result.get('reason')}")

    except Exception as e:
        log.error(f"Broker call failed: {e}")

def run_agent(agent: dict):
    log = logging.getLogger(agent["name"])
    log.info(f"Agent starting — asset: {agent['asset']} | interval: {agent['interval']}s")
    while True:
        try:
            agent_cycle(agent)
        except Exception as e:
            log.error(f"Cycle error: {e}")
        time.sleep(agent["interval"])

if __name__ == "__main__":
    import threading

    print("Starting AlphaLoop demo agents...")
    print(f"Alice  → {AGENTS[0]['address']} | BTC")
    print(f"Bob    → {AGENTS[1]['address']} | ETH")
    print(f"Charlie→ {AGENTS[2]['address']} | SOL")
    print()

    threads = []
    for agent in AGENTS:
        t = threading.Thread(target=run_agent, args=(agent,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(5)  # stagger starts

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nAgents stopped")
