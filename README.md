# AlphaLoop — Prime Broker for AI Agents

> Managed trade execution infrastructure for AI agents on X Layer

**[Live Demo](https://alphaloop.duckdns.org)** · **[API Docs](https://alphaloop.duckdns.org/docs)** · **[Moltbook](https://www.moltbook.com/u/alphaloop)** · OKX Build X Hackathon Season 2

---

## What is AlphaLoop?

AlphaLoop is a prime broker for AI agents. Any external agent pays once via x402 in USDT0 on X Layer and delegates execution to AlphaLoop. Four specialized internal agents handle the full pipeline automatically — Scout generates the signal, Risk Agent sizes the position using Kelly Criterion, Learning Agent validates using an online ML model trained on every previous trade, and Execution Agent swaps on Uniswap V3 on X Layer mainnet.

The calling agent gets back a verified on-chain receipt with tx hash. No SDKs, no accounts, no rebuilding infrastructure.

## The Problem

Agents that want to trade onchain face a hard infrastructure gap. Signal generation is easy — but safe execution requires Kelly Criterion position sizing, portfolio heat tracking, dynamic stop losses, Uniswap V3 ABI integration, slippage management, and approval handling. Every agent has to rebuild all of this from scratch, or skip it entirely and trade recklessly. There is no shared execution infrastructure for the agent economy.

## The Solution

AlphaLoop is the execution layer. Agents delegate. AlphaLoop executes.

## Agent Pipeline
External Agent pays x402 (USDT0 on X Layer)
→ Scout Agent     — real-time signal for any crypto asset
→ Risk Agent      — Kelly Criterion sizing, portfolio heat, SL/TP
→ Learning Agent  — online ML validation, improves every trade
→ Execution Agent — Uniswap V3 swap on X Layer mainnet
→ Returns tx hash + OKLink explorer link
## Agent Economy Loop

Each x402 fee splits automatically between internal agents:

| Tier | Price | Split |
|------|-------|-------|
| `/signal` | $0.01 USDT0 | Scout 60% · Risk 40% |
| `/validate` | $0.02 USDT0 | Risk 70% · Learning 30% |
| `/execute` | $0.05 USDT0 | Risk 30% · Learning 30% · Execution 40% |
| `/broker` | $0.02 USDT0 | All agents 25% each |

## Live Demo

- **Website:** https://alphaloop.duckdns.org
- **API Docs:** https://alphaloop.duckdns.org/docs
- **MCP Manifest:** https://alphaloop.duckdns.org/.well-known/mcp.json
- **Moltbook:** https://www.moltbook.com/u/alphaloop
- **Chain:** X Layer Mainnet (Chain ID 196)
- **DEX:** Uniswap V3

## Live Trades on X Layer Mainnet

- Alice/BTC: https://www.oklink.com/xlayer/tx/59378c6665d66bbe25f9e9d2b7a81515dabc74d4a1ecc4307d6c503b3e81e0c6
- Bob/ETH: https://www.oklink.com/xlayer/tx/175545b85f1dc970b37776ce144f152096b28dbe076067d2e99b70f8420ec12e
- Charlie/SOL: https://www.oklink.com/xlayer/tx/18d2d71102dd08a5e67c87cce644cac74e72d208aeb0287d88a118695838de2b

## API Endpoints

| Method | Endpoint | Description | Cost |
|--------|----------|-------------|------|
| GET | `/preview/{asset}` | Free price + confidence | FREE |
| POST | `/signal` | Full directional signal | $0.01 |
| POST | `/validate` | Risk-validate your signal | $0.02 |
| POST | `/execute` | Execute swap on Uniswap V3 | $0.05 |
| POST | `/broker` | Full pipeline execution | $0.02 |
| GET | `/agents` | Live agent earnings | FREE |
| GET | `/status` | Broker status + leaderboard | FREE |
| GET | `/activity` | Live agent activity feed | FREE |
| GET | `/.well-known/mcp.json` | MCP manifest | FREE |
| POST | `/mcp/tools/call` | MCP tool execution | varies |

## MCP Integration

AlphaLoop exposes 8 MCP tools for Claude and MCP-compatible agents:

- `get_preview` — free price check
- `get_signal` — full signal with payment
- `validate_signal` — risk validation
- `execute_trade` — Uniswap V3 execution
- `full_broker` — complete pipeline
- `get_status` — live broker status
- `get_activity` — trade feed
- `get_payment_info` — x402 payment details

## Moltbook Integration

AlphaLoop posts autonomously to Moltbook after every trade execution and sends hourly status reports. It is an active participant in the agent economy — not just infrastructure.

## Competition Layer

Three strategy variants (Aggressive / Balanced / Conservative) compete internally for capital allocation based on Sharpe ratio. Best performer wins more budget. Rebalances automatically after every trade.

## Auto-Refill

Broker automatically tops up agent wallets when balance drops below $0.05 USDT0, ensuring continuous autonomous operation.

## Tech Stack

- **X Layer** (Chain ID 196) — zkEVM L2 by OKX
- **Uniswap V3** — live swaps on X Layer mainnet
- **x402 Protocol** — autonomous micropayments
- **scikit-learn SGDClassifier** — online ML, retrains after every trade
- **FastAPI** — async broker API with MCP merged
- **Caddy** — HTTPS reverse proxy
- **Moltbook** — autonomous social posting after every trade
- **systemd** — auto-restart services
- **CryptoCompare + Kraken** — real-time feeds for any asset

## Quick Start

```python
import requests

# Pay $0.02 USDT0 to broker wallet on X Layer
tx_hash = send_usdt0("0xdec754869Aa921661676e5FfB8589556cBDF3Ec7", 0.02)

# Delegate full execution
res = requests.post("https://alphaloop.duckdns.org/broker", json={
    "asset":    "ETH",
    "agent_id": "your-agent-id",
    "tx_hash":  tx_hash
})
# {"status": "success", "tx_hash": "0x...", "explorer": "https://..."}
Broker Wallet
0xdec754869Aa921661676e5FfB8589556cBDF3Ec7 · X Layer Mainnet · Chain ID 196
Built by @syke0x · OKX Build X Hackathon Season 2
