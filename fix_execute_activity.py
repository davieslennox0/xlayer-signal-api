with open("prime_broker.py") as f:
    content = f.read()

old = '''        record_agent_earnings("execute", FEE_TIERS["execute"]["price_usdt"])
        return {
            "status": result["status"],
            "tx_hash": result["tx_hash"],
            "explorer": result["explorer"],
            "asset": asset,
            "direction": req.direction,
            "size_usdt": size,
            "agent_id": req.agent_id,'''

new = '''        record_agent_earnings("execute", FEE_TIERS["execute"]["price_usdt"])
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {
            "status": result["status"],
            "tx_hash": result["tx_hash"],
            "explorer": result["explorer"],
            "asset": asset,
            "direction": req.direction,
            "size_usdt": size,
            "agent_id": req.agent_id,'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
