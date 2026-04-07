import json
import time
import numpy as np
from pathlib import Path
from learning_agent import get_performance_stats, load_history

STRATEGIES = {
    "aggressive": {
        "confidence_bias": +10,   # lowers bar to fire
        "size_multiplier": 1.5,
        "min_confidence": 50,
    },
    "balanced": {
        "confidence_bias": 0,
        "size_multiplier": 1.0,
        "min_confidence": 55,
    },
    "conservative": {
        "confidence_bias": -10,   # raises bar to fire
        "size_multiplier": 0.6,
        "min_confidence": 65,
    },
}

ALLOCATION_PATH = "allocations.json"
STRATEGY_HISTORY_PATH = "strategy_history.json"

def load_allocations() -> dict:
    if Path(ALLOCATION_PATH).exists():
        with open(ALLOCATION_PATH) as f:
            return json.load(f)
    # Start equal
    base = round(1/len(STRATEGIES), 4)
    allocs = {s: base for s in STRATEGIES}
    # Fix rounding drift
    last = list(allocs.keys())[-1]
    allocs[last] = round(1 - base * (len(STRATEGIES) - 1), 4)
    return allocs

def save_allocations(allocs: dict):
    with open(ALLOCATION_PATH, "w") as f:
        json.dump(allocs, f, indent=2)

def load_strategy_history() -> dict:
    if Path(STRATEGY_HISTORY_PATH).exists():
        with open(STRATEGY_HISTORY_PATH) as f:
            return json.load(f)
    return {s: [] for s in STRATEGIES}

def save_strategy_history(history: dict):
    with open(STRATEGY_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

def record_strategy_trade(strategy: str, outcome: int, pnl_pct: float):
    history = load_strategy_history()
    history[strategy].append({
        "timestamp": int(time.time()),
        "outcome": outcome,
        "pnl_pct": pnl_pct
    })
    save_strategy_history(history)
    rebalance_allocations()

def get_strategy_sharpe(trades: list) -> float:
    if len(trades) < 2:
        return 0.0
    returns = [t["pnl_pct"] / 100 for t in trades]
    avg = np.mean(returns)
    std = np.std(returns) if np.std(returns) > 0 else 0.001
    return float((avg / std) * np.sqrt(252))

def rebalance_allocations():
    """Allocate capital proportional to each strategy's Sharpe ratio."""
    history = load_strategy_history()
    sharpes = {}

    for strategy, trades in history.items():
        sharpes[strategy] = max(get_strategy_sharpe(trades), 0.01)

    total = sum(sharpes.values())
    allocs = {s: sharpes[s] / total for s in sharpes}
    # Normalize to exactly 1.0
    total_alloc = sum(allocs.values())
    allocs = {s: round(v / total_alloc, 4) for s, v in allocs.items()}
    last = list(allocs.keys())[-1]
    allocs[last] = round(1 - sum(list(allocs.values())[:-1]), 4)
    save_allocations(allocs)
    return allocs

def select_strategy(signal: dict) -> tuple[str, dict, float]:
    """
    Returns (strategy_name, modified_signal, position_size_multiplier)
    Selects strategy weighted by current allocation.
    """
    allocs = load_allocations()
    names = list(allocs.keys())
    weights = [allocs[n] for n in names]

    # Weighted random selection — better strategies get picked more
    chosen = np.random.choice(names, p=weights)
    params = STRATEGIES[chosen]

    modified_signal = signal.copy()
    modified_signal["confidence"] = min(
        100, signal.get("confidence", 50) + params["confidence_bias"]
    )

    return chosen, modified_signal, params["size_multiplier"]

def get_leaderboard() -> list:
    history = load_strategy_history()
    allocs = load_allocations()
    board = []

    for strategy, trades in history.items():
        wins = sum(1 for t in trades if t["outcome"] == 1)
        total = len(trades)
        win_rate = round(wins / total * 100, 2) if total > 0 else 0
        total_pnl = round(sum(t["pnl_pct"] for t in trades), 4)
        sharpe = round(get_strategy_sharpe(trades), 4)

        board.append({
            "strategy":   strategy,
            "trades":     total,
            "win_rate":   win_rate,
            "total_pnl":  total_pnl,
            "sharpe":     sharpe,
            "allocation": round(allocs.get(strategy, 0) * 100, 1),
        })

    return sorted(board, key=lambda x: x["sharpe"], reverse=True)

if __name__ == "__main__":
    from signal_engine import generate_signal

    signal = generate_signal()
    strategy, modified_signal, size_mult = select_strategy(signal)

    print(f"Selected strategy: {strategy}")
    print(f"Size multiplier:   {size_mult}x")
    print(f"Original confidence: {signal.get('confidence')}")
    print(f"Modified confidence: {modified_signal.get('confidence')}")
    print(f"\nLeaderboard:")
    print(json.dumps(get_leaderboard(), indent=2))
    print(f"\nAllocations:")
    print(json.dumps(load_allocations(), indent=2))
