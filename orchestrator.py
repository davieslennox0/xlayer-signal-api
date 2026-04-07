import os
import time
import json
import logging
from dotenv import load_dotenv
from signal_engine import generate_signal, generate_eth_signal
from risk_agent import assess_risk, get_portfolio_value
from learning_agent import should_trade, record_outcome, get_performance_stats
from competition_layer import select_strategy, record_strategy_trade, get_leaderboard
from execution_agent import execute_swap

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alphaloop.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("AlphaLoop")

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 300))  # 5 min default
OPEN_TRADES = {}  # trade_id -> trade metadata

def run_cycle(signal_fn, asset_label):
    log.info(f"--- Scanning {asset_label} ---")

    # Step 1: Scout
    signal = signal_fn()
    direction = signal.get("direction")
    confidence = signal.get("confidence", 0)
    price = signal.get("price", 0)
    log.info(f"{asset_label} | price=${price} | direction={direction} | confidence={confidence}")

    # Step 2: Competition Layer picks strategy
    strategy, modified_signal, size_mult = select_strategy(signal)
    log.info(f"Strategy selected: {strategy} (size x{size_mult})")

    # Step 3: Learning Agent decides
    if not should_trade(modified_signal):
        log.info(f"Learning Agent: wait")
        return

    log.info(f"Learning Agent: fire")

    # Step 4: Risk Agent approves and sizes
    portfolio_value = get_portfolio_value()
    history = []  # loaded from trade history in full version
    risk = assess_risk(modified_signal, portfolio_value, history)

    if not risk["approved"]:
        log.info(f"Risk Agent: blocked — {risk['reason']}")
        return

    position_size = round(risk["position_size_usdt"] * size_mult, 4)
    log.info(f"Risk Agent: approved | size=${position_size} | SL={risk['stop_loss_pct']}% | TP={risk['take_profit_pct']}%")

    # Step 5: Execute
    try:
        result = execute_swap(asset_label, direction, position_size)
        log.info(f"Execution: {result['status']} | tx={result['tx_hash']}")
        log.info(f"Explorer: {result['explorer']}")

        if result["status"] == "success":
            trade_id = result["tx_hash"]
            OPEN_TRADES[trade_id] = {
                "signal": signal,
                "strategy": strategy,
                "direction": direction,
                "entry_price": price,
                "size_usdt": position_size,
                "stop_loss_pct": risk["stop_loss_pct"],
                "take_profit_pct": risk["take_profit_pct"],
                "opened_at": int(time.time()),
            }
            log.info(f"Trade opened: {trade_id}")

    except Exception as e:
        log.error(f"Execution failed: {e}")

def check_open_trades():
    """Check if open trades have hit SL or TP."""
    if not OPEN_TRADES:
        return

    # Get current prices
    try:
        btc_signal = generate_signal()
        eth_signal = generate_eth_signal()
        prices = {
            "BTC": btc_signal.get("price", 0),
            "ETH": eth_signal.get("price", 0),
            "OKB": btc_signal.get("price", 0),  # proxy
        }
    except Exception as e:
        log.error(f"Price fetch failed: {e}")
        return

    to_close = []
    for trade_id, trade in OPEN_TRADES.items():
        asset = trade["signal"].get("asset", "BTC")
        current_price = prices.get(asset, 0)
        if not current_price:
            continue

        entry = trade["entry_price"]
        direction = trade["direction"]
        sl_pct = trade["stop_loss_pct"] / 100
        tp_pct = trade["take_profit_pct"] / 100

        pnl_pct = (current_price - entry) / entry
        if direction.upper() == "DOWN":
            pnl_pct = -pnl_pct

        hit_tp = pnl_pct >= tp_pct
        hit_sl = pnl_pct <= -sl_pct

        if hit_tp or hit_sl:
            reason = "TP" if hit_tp else "SL"
            log.info(f"Closing trade {trade_id[:10]}... | {reason} hit | PnL={pnl_pct*100:.2f}%")

            closed = record_outcome(
                trade["signal"], entry, current_price,
                direction, trade["size_usdt"]
            )
            record_strategy_trade(
                trade["strategy"],
                closed["outcome"],
                closed["pnl_pct"]
            )
            to_close.append(trade_id)

    for t in to_close:
        del OPEN_TRADES[t]

def print_status():
    stats = get_performance_stats()
    board = get_leaderboard()
    log.info(f"=== AlphaLoop Status ===")
    log.info(f"Performance: {json.dumps(stats)}")
    log.info(f"Leader: {board[0]['strategy']} | Sharpe={board[0]['sharpe']} | Alloc={board[0]['allocation']}%")
    log.info(f"Open trades: {len(OPEN_TRADES)}")

def main():
    log.info("AlphaLoop starting...")
    log.info(f"Scan interval: {SCAN_INTERVAL}s")

    cycle = 0
    while True:
        try:
            run_cycle(generate_signal, "BTC")
            time.sleep(10)
            run_cycle(generate_eth_signal, "ETH")
            check_open_trades()

            cycle += 1
            if cycle % 12 == 0:  # print status every hour
                print_status()

        except KeyboardInterrupt:
            log.info("AlphaLoop stopped by user")
            print_status()
            break
        except Exception as e:
            log.error(f"Cycle error: {e}")

        log.info(f"Sleeping {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
