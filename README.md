# Trend Pilot — AI Signal Agent on X Layer

> Multi-asset AI signal API with x402 autonomous payments, built for the OKX X Layer Hackathon

## What is Trend Pilot?

Trend Pilot is an autonomous AI signal agent that provides real-time trading signals for BTC, ETH, XAUT (Gold), OKB, ZEC and BCH — powered by the x402 payment protocol on X Layer.

**Agents pay agents.** No humans required.

## How it works
External Agent requests signal
↓
Signal API responds with HTTP 402 (pay first)
↓
Agent pays $0.01 USDT on X Layer via x402
↓
Signal API verifies payment on-chain
↓
Full AI signal delivered instantly
↓
Agent executes trade on X Layer DEX
## Supported Assets

| Asset | Type | Source |
|-------|------|--------|
| BTC | Crypto | CryptoCompare + Kraken |
| ETH | Crypto | CryptoCompare + Kraken |
| XAUT | Tokenized Gold | CryptoCompare + Kraken |
| OKB | OKX Token | CryptoCompare |
| ZEC | Crypto | CryptoCompare |
| BCH | Crypto | CryptoCompare |

## Signal Engine

Each signal uses 5 indicators:
- **RSI** — momentum with asymmetric bias zones
- **VWAP** — volume-weighted fair value
- **Bollinger Bands** — volatility boundaries
- **Momentum** — 5-candle rate of change
- **Order Book** — bid/ask pressure ratio

Confidence score mapped to UP / DOWN / HOLD direction.

## API Endpoints

### Free Preview
GET /signal/{asset}/free
Returns price and confidence — direction locked behind payment.

### Full Signal (x402)
GET /signal/{asset}?tx=<payment_tx_hash>
Returns full signal with direction and all indicators.

### All Assets
GET /signals/all?tx=<payment_tx_hash>
Single payment covers all 6 assets.

## x402 Payment Flow

1. Agent calls `/signal/BTC`
2. Server responds `HTTP 402` with payment details
3. Agent sends `$0.01 USDT` to owner wallet on X Layer (Chain ID: 196)
4. Agent retries with `?tx=<hash>`
5. Signal delivered

## Tech Stack

- **FastAPI** — async signal API server
- **X Layer** — payment settlement (Chain ID: 196)
- **x402 protocol** — autonomous micropayments
- **Python** — signal engine (RSI, VWAP, BB, momentum, order book)
- **Kraken + CryptoCompare** — real-time price feeds

## Live Demo

Signal API: `http://108.61.91.153:8000`

Try the free preview:
```bash
curl http://108.61.91.153:8000/signal/BTC/free
curl http://108.61.91.153:8000/signal/XAUT/free
Built by
Trend Pilot — AI Trading Infrastructure

## Additional Endpoints

### Risk Score
GET /risk/{asset}?tx=<payment_tx_hash>
Returns volatility, trend direction, risk level (LOW/MEDIUM/HIGH) and momentum.

### On-chain Wallet Data
GET /onchain/{wallet}?tx=<payment_tx_hash>
Returns OKB balance, USDT0 balance and transaction count on X Layer.

### Trade Execution Calldata
POST /execute?tx=<payment_tx_hash>
Body: {"asset": "BTC", "direction": "up", "amount": 1.0, "wallet": "0x..."}
Returns ready-to-use approve calldata + current signal for the asset.
Cost: $0.05 USDT (5x signal price)
