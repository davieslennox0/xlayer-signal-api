with open("prime_broker.py") as f:
    content = f.read()

# Find the full broker endpoint and add logging after status check
old = '''        if status == "success":
            log.info(f"Trade executed: {result.get('explorer')}")
        elif status == "waiting":
            log.info(f"Agent waiting: {result.get('reason')}")
        else:
            log.info(f"Rejected: {result.get('reason')}")'''

new = '''        ACTIVITY_LOG.append({
            "agent_id": req.agent_id,
            "asset": asset,
            "status": status,
            "reason": result.get("reason", ""),
            "tx_hash": result.get("tx_hash", ""),
            "timestamp": int(__import__("time").time())
        })
        if status == "success":
            log.info(f"Trade executed: {result.get('explorer')}")
        elif status == "waiting":
            log.info(f"Agent waiting: {result.get('reason')}")
        else:
            log.info(f"Rejected: {result.get('reason')}")'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
