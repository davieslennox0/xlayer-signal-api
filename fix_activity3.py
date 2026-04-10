with open("prime_broker.py") as f:
    content = f.read()

# Move ACTIVITY_LOG to top and add logging in broker
content = content.replace(
    "# Activity log — stores recent agent calls\nACTIVITY_LOG = []",
    ""
)

content = content.replace(
    "AGENT_EARNINGS = {a: 0.0 for a in AGENT_WALLETS}",
    "AGENT_EARNINGS = {a: 0.0 for a in AGENT_WALLETS}\nACTIVITY_LOG = []"
)

content = content.replace(
    "    if not should_trade(modified_signal):\n        return {\"status\": \"waiting\", \"reason\": \"Conditions not met\", \"asset\": asset}",
    """    if not should_trade(modified_signal):
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "waiting", "timestamp": int(__import__("time").time())})
        return {"status": "waiting", "reason": "Conditions not met", "asset": asset}"""
)

content = content.replace(
    "    if not risk[\"approved\"]:\n        return {\"status\": \"rejected\", \"reason\": risk[\"reason\"]}",
    """    if not risk["approved"]:
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "rejected", "timestamp": int(__import__("time").time())})
        return {"status": "rejected", "reason": risk["reason"]}"""
)

content = content.replace(
    "        record_agent_earnings(\"full\", FEE_TIERS[\"full\"][\"price_usdt\"])",
    """        record_agent_earnings("full", FEE_TIERS["full"]["price_usdt"])
        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})"""
)

with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
