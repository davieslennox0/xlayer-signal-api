with open("prime_broker.py") as f:
    content = f.read()

old = '''        if result["status"] == "success":
            register_trade(
                tx_hash=result["tx_hash"],
                asset=asset,
                direction=req.direction,
                entry_price=sig_price if hasattr(req, "price") else 0,
                size_usdt=size,
                stop_loss_pct=1.5,
                take_profit_pct=3.0,
                strategy="balanced",
                signal={"asset": asset, "direction": req.direction,
                        "confidence": 65, "price": 0,
                        "rsi": 50, "momentum": 0, "ob_ratio": 1,
                        "bb_high": 0, "bb_low": 0, "vwap": 0}
            )'''

new = '''        if result["status"] == "success":
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
            )'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
