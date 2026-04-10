"""
AlphaLoop MCP Server
Exposes AlphaLoop Prime Broker as MCP tools for Claude and other MCP agents.
Runs on port 8001 alongside the main broker.
"""
import os
import json
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
from dotenv import load_dotenv

load_dotenv()

BROKER_URL = "http://localhost:8000"

app = FastAPI(
    title="AlphaLoop MCP Server",
    description="MCP interface for AlphaLoop Prime Broker",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MCP Protocol Endpoints ───────────────────────────────────────────────────

@app.get("/.well-known/mcp.json")
def mcp_manifest():
    """MCP discovery manifest."""
    return {
        "schema_version": "v1",
        "name": "alphaloop",
        "display_name": "AlphaLoop Prime Broker",
        "description": "Managed trade execution for AI agents on X Layer. Pay x402, get Uniswap V3 execution.",
        "url": "https://alphaloop.duckdns.org",
        "tools": [
            {
                "name": "get_preview",
                "description": "Get live price and confidence for any crypto asset. Free, no payment needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset": {"type": "string", "description": "Crypto ticker e.g. BTC, ETH, SOL, OKB"}
                    },
                    "required": ["asset"]
                }
            },
            {
                "name": "get_signal",
                "description": "Get full directional trading signal for an asset. Costs $0.01 USDT0 on X Layer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset":    {"type": "string", "description": "Crypto ticker"},
                        "tx_hash":  {"type": "string", "description": "Payment tx hash — send $0.01 USDT0 to broker wallet first"}
                    },
                    "required": ["asset", "tx_hash"]
                }
            },
            {
                "name": "validate_signal",
                "description": "Submit your own signal for Risk Agent validation. Returns position size, SL/TP. Costs $0.02 USDT0.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset":      {"type": "string"},
                        "direction":  {"type": "string", "enum": ["UP", "DOWN"]},
                        "confidence": {"type": "number", "description": "0-100"},
                        "tx_hash":    {"type": "string"}
                    },
                    "required": ["asset", "direction", "confidence", "tx_hash"]
                }
            },
            {
                "name": "execute_trade",
                "description": "Execute a Uniswap V3 swap on X Layer. Risk + Learning + Execution pipeline. Costs $0.05 USDT0.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset":       {"type": "string"},
                        "direction":   {"type": "string", "enum": ["UP", "DOWN"]},
                        "amount_usdt": {"type": "number", "description": "Trade size in USDT0"},
                        "agent_id":    {"type": "string"},
                        "tx_hash":     {"type": "string"}
                    },
                    "required": ["asset", "direction", "amount_usdt", "agent_id", "tx_hash"]
                }
            },
            {
                "name": "full_broker",
                "description": "Full pipeline — Scout, Risk, Learning, Execution all in one call. Costs $0.02 USDT0.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset":    {"type": "string"},
                        "agent_id": {"type": "string"},
                        "tx_hash":  {"type": "string"}
                    },
                    "required": ["asset", "agent_id", "tx_hash"]
                }
            },
            {
                "name": "get_status",
                "description": "Get live broker status — portfolio value, agent earnings, strategy leaderboard.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_activity",
                "description": "Get live agent activity feed — recent trades and signals.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_payment_info",
                "description": "Get broker wallet address and payment instructions for x402.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
    }

# ── Tool execution ────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    name: str
    parameters: dict = {}

@app.post("/mcp/tools/call")
async def call_tool(call: ToolCall):
    """Execute an MCP tool call."""
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            if call.name == "get_preview":
                r = await client.get(f"{BROKER_URL}/preview/{call.parameters['asset']}")
                return {"result": r.json()}

            elif call.name == "get_signal":
                r = await client.post(f"{BROKER_URL}/signal", json=call.parameters)
                return {"result": r.json()}

            elif call.name == "validate_signal":
                r = await client.post(f"{BROKER_URL}/validate", json=call.parameters)
                return {"result": r.json()}

            elif call.name == "execute_trade":
                r = await client.post(f"{BROKER_URL}/execute", json=call.parameters)
                return {"result": r.json()}

            elif call.name == "full_broker":
                r = await client.post(f"{BROKER_URL}/broker", json=call.parameters)
                return {"result": r.json()}

            elif call.name == "get_status":
                r = await client.get(f"{BROKER_URL}/status")
                return {"result": r.json()}

            elif call.name == "get_activity":
                r = await client.get(f"{BROKER_URL}/activity")
                return {"result": r.json()}

            elif call.name == "get_payment_info":
                return {"result": {
                    "broker_wallet": os.getenv("WALLET_ADDRESS"),
                    "chain":         "X Layer",
                    "chain_id":      196,
                    "token":         "USDT0",
                    "token_address": "0x779Ded0c9e1022225f8E0630b35a9b54bE713736",
                    "tiers": {
                        "signal":   "$0.01 USDT0",
                        "validate": "$0.02 USDT0",
                        "execute":  "$0.05 USDT0",
                        "broker":   "$0.02 USDT0"
                    }
                }}

            else:
                return {"error": f"Unknown tool: {call.name}"}

        except Exception as e:
            return {"error": str(e)}

@app.get("/mcp/tools")
def list_tools():
    """List available MCP tools."""
    manifest = mcp_manifest()
    return {"tools": manifest["tools"]}

@app.get("/")
def root():
    return {
        "name": "AlphaLoop MCP Server",
        "version": "1.0.0",
        "manifest": "/.well-known/mcp.json",
        "tools": "/mcp/tools",
        "execute": "/mcp/tools/call"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8001, reload=False)
