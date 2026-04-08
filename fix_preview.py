with open("prime_broker.py") as f:
    content = f.read()

old = "from signal_engine import generate_signal, generate_eth_signal"
new = "from signal_engine import generate_signal, generate_eth_signal, generate_any_signal"

old2 = '''@app.get("/preview/{asset}")
def preview(asset: str):
    """Free preview — price and direction locked."""
    asset = asset.upper()
    sig = generate_signal() if asset == "BTC" else generate_eth_signal()
    return {
        "asset": asset,
        "price": sig.get("price"),
        "confidence": sig.get("confidence"),
        "direction": "*** PAY $0.01 USDT0 TO UNLOCK ***",
        "payment_address": BROKER_WALLET,
        "chain_id": CHAIN_ID,
        "unlock_endpoint": f"/signal",
    }'''

new2 = '''@app.get("/preview/{asset}")
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
    }'''

# Also fix /signal and /broker endpoints to use generate_any_signal
old3 = '    sig = generate_signal() if asset == "BTC" else generate_eth_signal()\n    record_agent_earnings("signal", FEE_TIERS["signal"]["price_usdt"])'
new3 = '    sig = generate_any_signal(asset)\n    if "error" in sig:\n        raise HTTPException(status_code=404, detail=f"No data for {asset}")\n    record_agent_earnings("signal", FEE_TIERS["signal"]["price_usdt"])'

old4 = '    sig = generate_signal() if asset == "BTC" else generate_eth_signal()\n    strategy, modified_signal, size_mult = select_strategy(sig)'
new4 = '    sig = generate_any_signal(asset)\n    if "error" in sig:\n        raise HTTPException(status_code=404, detail=f"No data for {asset}")\n    strategy, modified_signal, size_mult = select_strategy(sig)'

content = content.replace(old, new).replace(old2, new2).replace(old3, new3).replace(old4, new4)

with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
