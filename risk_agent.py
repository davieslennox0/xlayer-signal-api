import os
import json
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://rpc.xlayer.tech")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

USDT0_ADDRESS = Web3.to_checksum_address("0x1E4a5963aBFD975d8c9021ce480b42188849D41d")
WALLET = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS"))
MAX_POSITION = float(os.getenv("MAX_POSITION_USDT", 2))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 20))

USDT0_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view"
    }
]

def get_portfolio_value():
    usdt0 = w3.eth.contract(address=USDT0_ADDRESS, abi=USDT0_ABI)
    balance = usdt0.functions.balanceOf(WALLET).call()
    return balance / 1e6

def kelly_position(win_rate: float, avg_win: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 0
    b = avg_win / avg_loss
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    return max(0, kelly * 0.5)

def assess_risk(signal: dict, portfolio_value: float, trade_history: list) -> dict:
    confidence = signal.get("confidence", 0) / 100
    direction = signal.get("direction", "HOLD")

    if direction == "HOLD":
        return {"approved": False, "reason": "Signal is HOLD"}

    if portfolio_value <= 0:
        return {"approved": False, "reason": "No portfolio value"}

    open_exposure = sum(t.get("size", 0) for t in trade_history if t.get("open"))
    heat = open_exposure / portfolio_value if portfolio_value > 0 else 1
    if heat > 0.8:
        return {"approved": False, "reason": f"Portfolio heat too high: {heat:.0%}"}

    wins = [t for t in trade_history if t.get("pnl", 0) > 0]
    losses = [t for t in trade_history if t.get("pnl", 0) < 0]
    win_rate = len(wins) / len(trade_history) if trade_history else confidence
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0.01
    avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 0.01

    fraction = kelly_position(win_rate, avg_win, avg_loss)
    raw_size = portfolio_value * fraction
    position_size = min(raw_size, MAX_POSITION)

    if position_size < 0.1:
        position_size = 0.5  # minimum viable demo size

    bb_width = signal.get("bb_upper", 0) - signal.get("bb_lower", 0)
    price = signal.get("price", 1)
    atr_pct = (bb_width / price) if price > 0 else 0.02

    stop_loss_pct = max(atr_pct * 0.5, 0.005)
    take_profit_pct = stop_loss_pct * 2

    return {
        "approved": True,
        "position_size_usdt": round(position_size, 4),
        "stop_loss_pct": round(stop_loss_pct * 100, 2),
        "take_profit_pct": round(take_profit_pct * 100, 2),
        "kelly_fraction": round(fraction, 4),
        "portfolio_heat": round(heat * 100, 2),
        "win_rate": round(win_rate * 100, 2),
        "reason": "Approved"
    }

if __name__ == "__main__":
    print(f"Connected: {w3.is_connected()}")
    print(f"Wallet: {WALLET}")
    pv = get_portfolio_value()
    print(f"Portfolio value: ${pv} USDT0")

    test_signal = {
        "asset": "ETH", "direction": "UP", "confidence": 72,
        "price": 3200, "bb_upper": 3280, "bb_lower": 3120
    }
    result = assess_risk(test_signal, pv, [])
    print(json.dumps(result, indent=2))
