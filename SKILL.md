---
name: alphaloop-prime-broker
description: >
  AlphaLoop is a prime broker for AI agents. Use this skill when an agent needs
  to trade crypto on X Layer without building risk management, position sizing,
  or Uniswap execution from scratch. Triggers on: execute a trade for BTC,
  swap ETH on X Layer, get a validated trading signal, size my position,
  validate my signal before trading, execute swap on Uniswap, trade SOL on
  X Layer, delegate trade execution, get signal with risk management.
license: MIT
version: 2.0.0
author: syke0x
api_url: https://alphaloop.duckdns.org
payment: x402 — USDT0 on X Layer (Chain ID 196)
broker_wallet: 0xdec754869Aa921661676e5FfB8589556cBDF3Ec7
---

# AlphaLoop — Prime Broker for AI Agents

Managed trade execution infrastructure for AI agents on X Layer.
Any agent pays once via x402 and gets back a verified on-chain execution receipt.

## What AlphaLoop Does For Your Agent

Your agent doesn't need to know about:
- Kelly Criterion position sizing
- Portfolio heat and risk management  
- Uniswap V3 ABIs and swap routing
- Slippage, approvals, and deadlines
- Stop loss and take profit calculation

AlphaLoop handles all of it. Your agent just pays and delegates.

## Agent Pipeline
Agent pays x402 (USDT0 on X Layer)
→ Scout Agent     — real-time signal for any crypto asset
→ Risk Agent      — Kelly Criterion sizing, portfolio heat, SL/TP
→ Learning Agent  — online ML validation, improves every trade
→ Execution Agent — Uniswap V3 swap on X Layer mainnet
→ Returns tx hash + OKLink explorer link
## Supported Assets

Any cryptocurrency supported by CryptoCompare — BTC, ETH, SOL, OKB, AVAX, DOT, LINK, UNI, ATOM, and more.

## Payment Tiers

| Endpoint | Cost | What You Get |
|----------|------|--------------|
| `/preview/{asset}` | FREE | Live price + confidence score |
| `/signal` | $0.01 USDT0 | Full directional signal + indicators |
| `/validate` | $0.02 USDT0 | Risk validation of your own signal |
| `/execute` | $0.05 USDT0 | Risk + Learning + Uniswap execution |
| `/broker` | $0.02 USDT0 | Full pipeline — signal to execution |
| `/agents` | FREE | Live agent earnings and status |
| `/status` | FREE | Portfolio, leaderboard, performance |
| `/activity` | FREE | Live agent activity feed |

## Agent Economy Loop

Each x402 fee splits automatically between AlphaLoop's internal agents:

- **Scout Agent** — earns 60% of signal fees
- **Risk Agent** — earns 30% of execution fees  
- **Learning Agent** — earns 30% of execution fees
- **Execution Agent** — earns 40% of execution fees

Agents paying agents. Onchain. Every trade.

## Usage Examples

### Free Preview (No Payment)

```bash
curl https://alphaloop.duckdns.org/preview/BTC
Response:
{
  "asset": "BTC",
  "price": 71477.46,
  "confidence": 67.2,
  "direction": "*** PAY $0.01 USDT0 TO UNLOCK ***",
  "payment_address": "0xdec754869Aa921661676e5FfB8589556cBDF3Ec7",
  "chain_id": 196
}
Full Broker Execution
import requests

# Step 1: pay $0.02 USDT0 to broker wallet on X Layer (Chain ID 196)
tx_hash = send_usdt0("0xdec754869Aa921661676e5FfB8589556cBDF3Ec7", 0.02)

# Step 2: delegate full execution
res = requests.post("https://alphaloop.duckdns.org/broker", json={
    "asset":    "ETH",
    "agent_id": "your-agent-id",
    "tx_hash":  tx_hash
})

# Step 3: get back on-chain receipt
# {"status": "success", "tx_hash": "0x...", "explorer": "https://..."}
print(res.json())
Signal Only
# Pay $0.01, get full signal
res = requests.post("https://alphaloop.duckdns.org/signal", json={
    "asset":    "SOL",
    "tx_hash":  tx_hash
})
# {"direction": "UP", "confidence": 71.2, "rsi": 58.3, "tradeable": true}
Validate Your Own Signal
# Pay $0.02, get Risk Agent validation
res = requests.post("https://alphaloop.duckdns.org/validate", json={
    "asset":      "BTC",
    "direction":  "UP",
    "confidence": 68.0,
    "tx_hash":    tx_hash
})
# {"approved": true, "suggested_size_usdt": 1.25, "stop_loss_pct": 1.2}
Live Demo
Website: https://alphaloop.duckdns.org
API Docs: https://alphaloop.duckdns.org/docs
Chain: X Layer Mainnet (Chain ID 196)
DEX: Uniswap V3
Tech Stack
X Layer (Chain ID 196) — zkEVM L2 by OKX
Uniswap V3 — live swaps on X Layer mainnet
x402 Protocol — autonomous micropayments
scikit-learn SGDClassifier — online ML, retrains on every trade
FastAPI — async broker API
RSI, VWAP, Bollinger Bands, Momentum, Order Book — signal engine
CryptoCompare + Kraken — real-time feeds for any asset
GitHub
https://github.com/davieslennox0/xlayer-signal-api
