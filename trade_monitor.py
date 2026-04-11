import os
import time
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

from signal_engine import generate_signal, generate_eth_signal, generate_any_signal
from learning_agent import record_outcome, load_history, save_history
from competition_layer import record_strategy_trade

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Monitor] %(message)s",
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("Monitor")

OPEN_TRADES_FILE = "open_trades.json"

def load_open_trades():
    if Path(OPEN_TRADES_FILE).exists():
        with open(OPEN_TRADES_FILE) as f:
            return json.load(f)
    return {}

def save_open_trades(trades):
    with open(OPEN_TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def register_trade(tx_hash, asset, direction, entry_price, size_usdt,
                   stop_loss_pct, take_profit_pct, strategy, signal):
    trades = load_open_trades()
    trades[tx_hash] = {
        "asset":           asset,
        "direction":       direction,
        "entry_price":     entry_price,
        "size_usdt":       size_usdt,
        "stop_loss_pct":   stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "strategy":        strategy,
        "signal":          signal,
        "opened_at":       int(time.time()),
    }
    save_open_trades(trades)
    log.info(f"Registered open trade: {tx_hash[:12]}... {asset} {direction} @ ${entry_price}")

def get_current_price(asset):
    try:
        if asset == "BTC":
            sig = generate_signal()
        elif asset == "ETH":
            sig = generate_eth_signal()
        else:
            sig = generate_any_signal(asset)
        return sig.get("price", 0)
    except Exception as e:
        log.error(f"Price fetch error for {asset}: {e}")
        return 0

def check_trades():
    trades = load_open_trades()
    if not trades:
        return

    to_close = []

    for tx_hash, trade in trades.items():
        asset        = trade["asset"]
        direction    = trade["direction"]
        entry        = trade["entry_price"]
        sl_pct       = trade["stop_loss_pct"] / 100
        tp_pct       = trade["take_profit_pct"] / 100
        size         = trade["size_usdt"]
        strategy     = trade["strategy"]
        signal       = trade["signal"]

        current = get_current_price(asset)
        if not current:
            continue

        pnl_pct = (current - entry) / entry
        if direction.upper() == "DOWN":
            pnl_pct = -pnl_pct

        age_hours = (int(time.time()) - trade["opened_at"]) / 3600

        hit_tp   = pnl_pct >= tp_pct
        hit_sl   = pnl_pct <= -sl_pct
        hit_time = age_hours >= 24  # force close after 24h

        if hit_tp or hit_sl or hit_time:
            reason = "TP" if hit_tp else "SL" if hit_sl else "TIME"
            log.info(f"Closing {tx_hash[:12]}... | {reason} | {asset} | PnL={pnl_pct*100:.2f}%")

            closed = record_outcome(signal, entry, current, direction, size)
            record_strategy_trade(strategy, closed["outcome"], closed["pnl_pct"])
            to_close.append(tx_hash)

            log.info(f"Outcome: {'WIN' if closed['outcome'] == 1 else 'LOSS'} | PnL=${closed['pnl_usdt']:.4f}")

    for tx in to_close:
        del trades[tx]
    save_open_trades(trades)

def run():
    log.info("Trade monitor started")
    while True:
        try:
            check_trades()
        except Exception as e:
            log.error(f"Monitor error: {e}")
        time.sleep(180)  # check every 3 minutes

if __name__ == "__main__":
    run()
