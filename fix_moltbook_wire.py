with open("prime_broker.py") as f:
    content = f.read()

old = "from trade_monitor import register_trade"
new = """from trade_monitor import register_trade
from moltbook_agent import post_trade"""

old2 = '''        if result["status"] == "success":
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

new2 = '''        if result["status"] == "success":
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
                log.error(f"Moltbook post error: {e}")'''

content = content.replace(old, new).replace(old2, new2)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
