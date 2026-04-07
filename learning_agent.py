import os
import json
import time
import pickle
from pathlib import Path
from dotenv import load_dotenv
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import NotFittedError
import numpy as np

load_dotenv()

MODEL_PATH = "alphaloop_model.pkl"
SCALER_PATH = "alphaloop_scaler.pkl"
HISTORY_PATH = "trade_history.json"

def load_history():
    if Path(HISTORY_PATH).exists():
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

def load_model():
    if Path(MODEL_PATH).exists() and Path(SCALER_PATH).exists():
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        return model, scaler
    model = SGDClassifier(loss="log_loss", learning_rate="adaptive",
                          eta0=0.01, random_state=42)
    scaler = StandardScaler()
    return model, scaler

def save_model(model, scaler):
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

def signal_to_features(signal: dict) -> np.ndarray:
    bb_width = signal.get("bb_high", 0) - signal.get("bb_low", 0)
    ob_ratio = signal.get("ob_ratio") or 1.0
    price = signal.get("price", 0)
    vwap = signal.get("vwap", 0)
    return np.array([[
        signal.get("rsi", 50),
        signal.get("confidence", 50),
        signal.get("momentum", 0),
        ob_ratio,
        1 if price > vwap else 0,
        bb_width,
    ]])

def should_trade(signal: dict) -> bool:
    direction = signal.get("direction")
    if not direction or direction.upper() == "HOLD":
        return False

    model, scaler = load_model()
    history = load_history()
    features = signal_to_features(signal)

    try:
        features_scaled = scaler.transform(features)
        proba = model.predict_proba(features_scaled)[0]
        win_probability = proba[1]
        ml_weight = min(len(history) / 50, 0.8)
        base = signal.get("confidence", 50) / 100
        blended = (base * (1 - ml_weight)) + (win_probability * ml_weight)
        return blended > 0.55

    except NotFittedError:
        return signal.get("confidence", 0) > 55

def record_outcome(signal: dict, entry_price: float, exit_price: float,
                   direction: str, size_usdt: float):
    history = load_history()

    pnl = (exit_price - entry_price) / entry_price
    if direction.upper() == "DOWN":
        pnl = -pnl
    pnl_usdt = pnl * size_usdt
    outcome = 1 if pnl > 0 else 0

    trade = {
        "timestamp": int(time.time()),
        "asset": signal.get("asset"),
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_pct": round(pnl * 100, 4),
        "pnl_usdt": round(pnl_usdt, 4),
        "size_usdt": size_usdt,
        "outcome": outcome,
        "open": False,
        "pnl": pnl_usdt,
        "signal_snapshot": signal
    }
    history.append(trade)
    save_history(history)

    model, scaler = load_model()
    X = np.vstack([signal_to_features(t["signal_snapshot"]) for t in history])
    y = np.array([t["outcome"] for t in history])
    X_scaled = scaler.fit_transform(X)
    model.partial_fit(X_scaled, y, classes=[0, 1])
    save_model(model, scaler)

    return trade

def get_performance_stats() -> dict:
    history = load_history()
    if not history:
        return {"trades": 0}

    closed = [t for t in history if not t.get("open")]
    if not closed:
        return {"trades": 0}

    total_pnl = sum(t["pnl_usdt"] for t in closed)
    wins = [t for t in closed if t["outcome"] == 1]
    win_rate = len(wins) / len(closed) * 100
    returns = [t["pnl_pct"] / 100 for t in closed]
    avg_return = np.mean(returns)
    std_return = np.std(returns) if len(returns) > 1 else 0.001
    sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0

    return {
        "trades": len(closed),
        "win_rate": round(win_rate, 2),
        "total_pnl_usdt": round(total_pnl, 4),
        "sharpe_ratio": round(sharpe, 4),
    }

if __name__ == "__main__":
    from signal_engine import generate_signal
    signal = generate_signal()
    decision = should_trade(signal)
    print(f"Asset: {signal.get('asset')} | Direction: {signal.get('direction')} | Fire: {decision}")
    print(json.dumps(get_performance_stats(), indent=2))
