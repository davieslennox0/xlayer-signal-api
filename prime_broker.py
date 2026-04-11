import os
import time
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from web3 import Web3

from signal_engine import generate_signal, generate_eth_signal, generate_any_signal
from trade_monitor import register_trade
from moltbook_agent import post_trade
from risk_agent import assess_risk, get_portfolio_value
from learning_agent import should_trade, record_outcome, get_performance_stats
from competition_layer import select_strategy, record_strategy_trade, get_leaderboard
from execution_agent import execute_swap

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AlphaLoop")

app = FastAPI(
    title="AlphaLoop Prime Broker",
    description="Managed trade execution infrastructure for AI agents.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
BROKER_WALLET = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS"))
CHAIN_ID = int(os.getenv("CHAIN_ID", 196))
USDT0 = Web3.to_checksum_address("0x779Ded0c9e1022225f8E0630b35a9b54bE713736")

# x402 fee splits
FEE_TIERS = {
    "signal":    {"price_usdt": 0.01, "splits": {"scout": 0.6, "risk": 0.4}},
    "validate":  {"price_usdt": 0.02, "splits": {"risk": 0.7, "learning": 0.3}},
    "execute":   {"price_usdt": 0.05, "splits": {"risk": 0.3, "learning": 0.3, "execution": 0.4}},
    "full":      {"price_usdt": 0.02, "splits": {"scout": 0.25, "risk": 0.25, "learning": 0.25, "execution": 0.25}},
}

# Agent wallet registry — each internal agent has its own address for splits
AGENT_WALLETS = {
    "scout":     BROKER_WALLET,  # single wallet for now, split tracked off-chain
    "risk":      BROKER_WALLET,
    "learning":  BROKER_WALLET,
    "execution": BROKER_WALLET,
}

AGENT_EARNINGS = {a: 0.0 for a in AGENT_WALLETS}
import json as _json
from pathlib import Path as _Path

_ACTIVITY_FILE = "activity_log.json"

def _load_activity():
    if _Path(_ACTIVITY_FILE).exists():
        try:
            with open(_ACTIVITY_FILE) as f:
                return _json.load(f)
        except:
            pass
    return []

def _save_activity(log):
    with open(_ACTIVITY_FILE, "w") as f:
        _json.dump(log[-100:], f)

ACTIVITY_LOG = _load_activity()

ERC20_ABI = [
    {"inputs":[{"name":"account","type":"address"}],
     "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
     "type":"function","stateMutability":"view"},
    {"inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],
     "name":"transferFrom","outputs":[{"name":"","type":"bool"}],
     "type":"function","stateMutability":"nonpayable"}
]

def verify_x402_payment(tx_hash: str, expected_usdt: float) -> bool:
    """Verify that tx_hash is a valid confirmed tx on X Layer."""
    import time
    try:
        for _ in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt and receipt["status"] == 1:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False
    except Exception as e:
        log.error(f"Payment verification error: {e}")
        return False

def record_agent_earnings(tier: str, total_usdt: float):
    splits = FEE_TIERS[tier]["splits"]
    for agent, fraction in splits.items():
        AGENT_EARNINGS[agent] = round(AGENT_EARNINGS.get(agent, 0) + total_usdt * fraction, 6)

# ── Models ──────────────────────────────────────────────────────────────────

class SignalRequest(BaseModel):
    asset: str = "BTC"
    tx_hash: str

class ValidateRequest(BaseModel):
    asset: str
    direction: str
    confidence: float
    tx_hash: str

class ExecuteRequest(BaseModel):
    asset: str
    direction: str
    amount_usdt: float
    agent_id: str
    tx_hash: str

class FullBrokerRequest(BaseModel):
    asset: str = "BTC"
    agent_id: str
    tx_hash: str

# ── Free endpoints ───────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "AlphaLoop Prime Broker",
        "tagline": "Managed trade execution infrastructure for AI agents",
        "chain": "X Layer (Chain ID 196)",
        "version": "2.0.0",
        "tiers": {k: f"${v['price_usdt']} USDT0" for k, v in FEE_TIERS.items()},
        "broker_wallet": BROKER_WALLET,
        "docs": "/docs"
    }

@app.get("/status")
def status():
    pv = get_portfolio_value()
    stats = get_performance_stats()
    board = get_leaderboard()
    return {
        "portfolio_value_usdt": pv,
        "performance": stats,
        "leaderboard": board,
        "agent_earnings": AGENT_EARNINGS,
        "open_trades": 0,
    }

@app.get("/preview/{asset}")
def preview(asset: str):
    """Free preview — price and direction locked."""
    asset = asset.upper()
    sig = generate_any_signal(asset)
    if "error" in sig:
        raise HTTPException(status_code=404, detail=f"No data for {asset}")
    return {
        "asset": asset,
        "price": sig.get("price"),
        "confidence": sig.get("confidence"),
        "direction": "*** PAY $0.01 USDT0 TO UNLOCK ***",
        "payment_address": BROKER_WALLET,
        "chain_id": CHAIN_ID,
        "unlock_endpoint": "/signal",
    }

# ── Tier 1: Signal only ──────────────────────────────────────────────────────

@app.post("/signal")
def get_signal(req: SignalRequest):
    """$0.01 — Scout + Risk Agent signal for requested asset."""
    if not verify_x402_payment(req.tx_hash, FEE_TIERS["signal"]["price_usdt"]):
        raise HTTPException(status_code=402, detail={
            "error": "Payment required",
            "amount": "0.01 USDT0",
            "to": BROKER_WALLET,
            "chain_id": CHAIN_ID,
            "token": USDT0,
        })

    asset = req.asset.upper()
    sig = generate_any_signal(asset)
    if "error" in sig:
        raise HTTPException(status_code=404, detail=f"No data for {asset}")
    record_agent_earnings("signal", FEE_TIERS["signal"]["price_usdt"])

    return {
        "asset": asset,
        "price": sig.get("price"),
        "direction": sig.get("direction"),
        "confidence": sig.get("confidence"),
        "rsi": sig.get("rsi"),
        "momentum": sig.get("momentum"),
        "tradeable": sig.get("tradeable"),
        "paid": True,
        "agent_earnings": {
            "scout": FEE_TIERS["signal"]["price_usdt"] * 0.6,
            "risk":  FEE_TIERS["signal"]["price_usdt"] * 0.4,
        }
    }

# ── Tier 2: Validate ─────────────────────────────────────────────────────────

@app.post("/validate")
def validate(req: ValidateRequest):
    """$0.02 — Risk Agent validates an external agent's own signal."""
    if not verify_x402_payment(req.tx_hash, FEE_TIERS["validate"]["price_usdt"]):
        raise HTTPException(status_code=402, detail={
            "error": "Payment required",
            "amount": "0.02 USDT0",
            "to": BROKER_WALLET,
            "chain_id": CHAIN_ID,
        })

    signal = {
        "asset": req.asset,
        "direction": req.direction,
        "confidence": req.confidence,
        "price": 0,
    }
    pv = get_portfolio_value()
    risk = assess_risk(signal, max(pv, 10), [])
    record_agent_earnings("validate", FEE_TIERS["validate"]["price_usdt"])

    return {
        "approved": risk["approved"],
        "reason": risk["reason"],
        "suggested_size_usdt": risk.get("position_size_usdt"),
        "stop_loss_pct": risk.get("stop_loss_pct"),
        "take_profit_pct": risk.get("take_profit_pct"),
        "agent_earnings": {
            "risk":     FEE_TIERS["validate"]["price_usdt"] * 0.7,
            "learning": FEE_TIERS["validate"]["price_usdt"] * 0.3,
        }
    }

# ── Tier 3: Full execution ───────────────────────────────────────────────────

@app.post("/execute")
def execute(req: ExecuteRequest):
    """$0.05 — Risk + Learning + Uniswap execution on X Layer."""
    if not verify_x402_payment(req.tx_hash, FEE_TIERS["execute"]["price_usdt"]):
        raise HTTPException(status_code=402, detail={
            "error": "Payment required",
            "amount": "0.05 USDT0",
            "to": BROKER_WALLET,
            "chain_id": CHAIN_ID,
        })

    asset = req.asset.upper()
    signal = {"asset": asset, "direction": req.direction, "confidence": 70, "price": 0}
    pv = get_portfolio_value()
    risk = assess_risk(signal, max(pv, 10), [])

    if not risk["approved"]:
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "rejected", "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {"status": "rejected", "reason": risk["reason"]}

    size = min(req.amount_usdt, risk["position_size_usdt"])

    try:
        result = execute_swap(asset, req.direction, size)
        record_agent_earnings("execute", FEE_TIERS["execute"]["price_usdt"])
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        if result["status"] == "success":
            live_sig = generate_any_signal(asset)
            live_price = live_sig.get("price", 0)
            register_trade(
                tx_hash=result["tx_hash"],
                asset=asset,
                direction=req.direction,
                entry_price=live_price,
                size_usdt=size,
                stop_loss_pct=1.5,
                take_profit_pct=3.0,
                strategy="balanced",
                signal=live_sig
            )
            try:
                post_trade(asset, req.direction, size, result["tx_hash"], result["status"])
            except Exception as e:
                log.error(f"Moltbook post error: {e}")
        return {
            "status": result["status"],
            "tx_hash": result["tx_hash"],
            "explorer": result["explorer"],
            "asset": asset,
            "direction": req.direction,
            "size_usdt": size,
            "agent_id": req.agent_id,
            "agent_earnings": {
                "risk":      FEE_TIERS["execute"]["price_usdt"] * 0.3,
                "learning":  FEE_TIERS["execute"]["price_usdt"] * 0.3,
                "execution": FEE_TIERS["execute"]["price_usdt"] * 0.4,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Tier 4: Full broker ──────────────────────────────────────────────────────

@app.post("/broker")
def full_broker(req: FullBrokerRequest):
    """$0.10 — Full pipeline: Scout → Risk → Learning → Uniswap execution."""
    if not verify_x402_payment(req.tx_hash, FEE_TIERS["full"]["price_usdt"]):
        raise HTTPException(status_code=402, detail={
            "error": "Payment required",
            "amount": "0.10 USDT0",
            "to": BROKER_WALLET,
            "chain_id": CHAIN_ID,
        })

    asset = req.asset.upper()
    sig = generate_any_signal(asset)
    if "error" in sig:
        raise HTTPException(status_code=404, detail=f"No data for {asset}")
    strategy, modified_signal, size_mult = select_strategy(sig)

    if not should_trade(modified_signal):
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "waiting", "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {"status": "waiting", "reason": "Conditions not met", "asset": asset}

    pv = get_portfolio_value()
    risk = assess_risk(modified_signal, max(pv, 10), [])

    if not risk["approved"]:
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "rejected", "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {"status": "rejected", "reason": risk["reason"]}

    size = round(risk["position_size_usdt"] * size_mult, 4)

    try:
        result = execute_swap(asset, sig.get("direction", "UP"), size)
        record_agent_earnings("full", FEE_TIERS["full"]["price_usdt"])
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {
            "status": result["status"],
            "tx_hash": result["tx_hash"],
            "explorer": result["explorer"],
            "asset": asset,
            "direction": sig.get("direction"),
            "confidence": sig.get("confidence"),
            "strategy": strategy,
            "size_usdt": size,
            "agent_id": req.agent_id,
            "agent_earnings": {a: round(FEE_TIERS["full"]["price_usdt"] * s, 4)
                               for a, s in FEE_TIERS["full"]["splits"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
def agent_status():
    return {
        "agents": [
            {"name": "Scout",     "role": "Signal generation",     "earnings_usdt": AGENT_EARNINGS["scout"]},
            {"name": "Risk",      "role": "Position sizing & SL/TP","earnings_usdt": AGENT_EARNINGS["risk"]},
            {"name": "Learning",  "role": "ML trade validation",    "earnings_usdt": AGENT_EARNINGS["learning"]},
            {"name": "Execution", "role": "Uniswap V3 on X Layer",  "earnings_usdt": AGENT_EARNINGS["execution"]},
        ],
        "total_earned_usdt": round(sum(AGENT_EARNINGS.values()), 6),
        "broker_wallet": BROKER_WALLET,
        "chain": "X Layer",
        "chain_id": CHAIN_ID,
    }

def run_monitor():
    import time
    from trade_monitor import check_trades
    while True:
        try:
            check_trades()
        except Exception as e:
            log.error(f"Monitor error: {e}")
        time.sleep(180)

@app.on_event("startup")
async def startup():
    import threading
    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()
    log.info("Trade monitor started as background thread")
    t2 = threading.Thread(target=run_moltbook_heartbeat, daemon=True)
    t2.start()
    log.info("Moltbook heartbeat started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("prime_broker:app", host="0.0.0.0", port=8000, reload=False)



@app.get("/activity")
def activity():
    return {"activity": ACTIVITY_LOG[-20:]}

# ── MCP Integration ──────────────────────────────────────────────────────────

@app.get("/.well-known/mcp.json")
def mcp_manifest():
    return {
        "schema_version": "v1",
        "name": "alphaloop",
        "display_name": "AlphaLoop Prime Broker",
        "description": "Managed trade execution for AI agents on X Layer. Pay x402, get Uniswap V3 execution.",
        "url": "https://alphaloop.duckdns.org",
        "tools": [
            {"name": "get_preview", "description": "Free price + confidence for any asset.", "parameters": {"type": "object", "properties": {"asset": {"type": "string"}}, "required": ["asset"]}},
            {"name": "get_signal", "description": "Full signal. Costs $0.01 USDT0.", "parameters": {"type": "object", "properties": {"asset": {"type": "string"}, "tx_hash": {"type": "string"}}, "required": ["asset", "tx_hash"]}},
            {"name": "validate_signal", "description": "Risk validation. Costs $0.02 USDT0.", "parameters": {"type": "object", "properties": {"asset": {"type": "string"}, "direction": {"type": "string"}, "confidence": {"type": "number"}, "tx_hash": {"type": "string"}}, "required": ["asset", "direction", "confidence", "tx_hash"]}},
            {"name": "execute_trade", "description": "Uniswap V3 execution. Costs $0.05 USDT0.", "parameters": {"type": "object", "properties": {"asset": {"type": "string"}, "direction": {"type": "string"}, "amount_usdt": {"type": "number"}, "agent_id": {"type": "string"}, "tx_hash": {"type": "string"}}, "required": ["asset", "direction", "amount_usdt", "agent_id", "tx_hash"]}},
            {"name": "full_broker", "description": "Full pipeline. Costs $0.02 USDT0.", "parameters": {"type": "object", "properties": {"asset": {"type": "string"}, "agent_id": {"type": "string"}, "tx_hash": {"type": "string"}}, "required": ["asset", "agent_id", "tx_hash"]}},
            {"name": "get_status", "description": "Live broker status.", "parameters": {"type": "object", "properties": {}}},
            {"name": "get_activity", "description": "Live activity feed.", "parameters": {"type": "object", "properties": {}}},
            {"name": "get_payment_info", "description": "Payment instructions.", "parameters": {"type": "object", "properties": {}}}
        ]
    }

@app.get("/mcp/tools")
def mcp_list_tools():
    return {"tools": mcp_manifest()["tools"]}

class MCPToolCall(BaseModel):
    name: str
    parameters: dict = {}

@app.post("/mcp/tools/call")
async def mcp_call_tool(call: MCPToolCall):
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            if call.name == "get_preview":
                r = await client.get(f"http://127.0.0.1:8000/preview/{call.parameters['asset']}")
                return {"result": r.json()}
            elif call.name == "get_signal":
                r = await client.post(f"http://127.0.0.1:8000/signal", json=call.parameters)
                return {"result": r.json()}
            elif call.name == "validate_signal":
                r = await client.post(f"http://127.0.0.1:8000/validate", json=call.parameters)
                return {"result": r.json()}
            elif call.name == "execute_trade":
                r = await client.post(f"http://127.0.0.1:8000/execute", json=call.parameters)
                return {"result": r.json()}
            elif call.name == "full_broker":
                r = await client.post(f"http://127.0.0.1:8000/broker", json=call.parameters)
                return {"result": r.json()}
            elif call.name == "get_status":
                r = await client.get(f"http://127.0.0.1:8000/status")
                return {"result": r.json()}
            elif call.name == "get_activity":
                r = await client.get(f"http://127.0.0.1:8000/activity")
                return {"result": r.json()}
            elif call.name == "get_payment_info":
                return {"result": {
                    "broker_wallet": BROKER_WALLET,
                    "chain_id": CHAIN_ID,
                    "token": "USDT0",
                    "token_address": USDT0,
                    "tiers": {"signal": "$0.01", "validate": "$0.02", "execute": "$0.05", "broker": "$0.02"}
                }}
            else:
                return {"error": f"Unknown tool: {call.name}"}
        except Exception as e:
            return {"error": str(e)}

def run_moltbook_heartbeat():
    """Post status to Moltbook every hour."""
    import time
    from moltbook_agent import post_status
    time.sleep(300)  # wait 5 min before first post
    cycle = 0
    while True:
        try:
            if cycle % 12 == 0:  # every hour (12 x 5min)
                pv = get_portfolio_value()
                stats = get_performance_stats()
                post_status(pv, AGENT_EARNINGS, stats.get("trades", 0))
                log.info("Moltbook status posted")
        except Exception as e:
            log.error(f"Moltbook heartbeat error: {e}")
        time.sleep(300)
        cycle += 1
