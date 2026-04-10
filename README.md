# AlphaLoop — Prime Broker for AI Agents

> Managed trade execution infrastructure for AI agents on X Layer

**[Live Demo](https://alphaloop.duckdns.org)** · **[API Docs](https://alphaloop.duckdns.org/docs)** · OKX Build X Hackathon Season 2

---

## What is AlphaLoop?

AlphaLoop is a prime broker that handles everything AI agents can't — risk management, position sizing, ML validation, and live Uniswap V3 execution on X Layer mainnet.

External agents pay once via x402. AlphaLoop handles the rest. No SDKs, no accounts, no API keys.

## The Problem

Agents that want to trade onchain face a hard problem: signal generation is easy, but safe execution is not. Every agent building a trading strategy has to rebuild risk management, position sizing, slippage math, Uniswap ABIs, and stop-loss logic from scratch.

AlphaLoop solves this. Agents delegate execution. AlphaLoop executes safely.

## Live Demo

- **Website:** https://alphaloop.duckdns.org
- **API:** https://alphaloop.duckdns.org/docs
- **Chain:** X Layer Mainnet (Chain ID 196)
- **DEX:** Uniswap V3
- **Active agents:** Alice (BTC), Bob (ETH), Charlie (SOL)

### Live Trades on X Layer Mainnet
- Alice: https://www.oklink.com/xlayer/tx/59378c6665d66bbe25f9e9d2b7a81515dabc74d4a1ecc4307d6c503b3e81e0c6
- Bob: https://www.oklink.com/xlayer/tx/175545b85f1dc970b37776ce144f152096b28dbe076067d2e99b70f8420ec12e
- Charlie: https://www.oklink.com/xlayer/tx/18d2d71102dd08a5e67c87cce644cac74e72d208aeb0287d88a118695838de2b

## Agent Pipeline
External Agent pays x402
→ Scout Agent     — signal for any crypto (RSI, VWAP, BB, momentum, OB)
→ Risk Agent      — Kelly Criterion sizing, portfolio heat, dynamic SL/TP
→ Learning Agent  — online ML model, improves with every trade
→ Execution Agent — Uniswap V3 swap on X Layer mainnet
→ Receipt returned with tx hash + OKLink explorer link
## Agent Economy Loop

Each x402 fee splits automatically between internal agents:

| Tier | Price | Split |
|------|-------|-------|
| `/signal` | $0.01 USDT0 | Scout 60% · Risk 40% |
| `/validate` | $0.02 USDT0 | Risk 70% · Learning 30% |
| `/execute` | $0.05 USDT0 | Risk 30% · Learning 30% · Execution 40% |
| `/broker` | $0.02 USDT0 | All agents 25% each |

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

## Competition Layer

Three strategy variants (Aggressive / Balanced / Conservative) compete internally for capital allocation. Best Sharpe ratio wins more budget. Rebalances automatically after every trade.

## Auto-Refill

Broker automatically tops up agent wallets when balance drops below $0.05 USDT0, ensuring continuous autonomous operation.

## Tech Stack

- **X Layer** — Chain ID 196, zkEVM L2 by OKX
- **Uniswap V3** — Live swaps on X Layer mainnet
- **x402 Protocol** — Autonomous micropayments
- **scikit-learn** — Online ML (SGDClassifier) for trade validation
- **FastAPI** — Async broker API
- **Caddy** — HTTPS reverse proxy
- **Python** — Signal engine (RSI, VWAP, BB, momentum, order book)
- **CryptoCompare + Kraken** — Real-time price feeds for any asset

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
