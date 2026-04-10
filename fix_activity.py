with open("prime_broker.py") as f:
    content = f.read()

old = '        log.info(f"Broker response: {result[\'status\']}")\n        return {'
new = '''        ACTIVITY_LOG.append({
            "agent_id": req.agent_id,
            "asset": asset,
            "status": result.get("status"),
            "timestamp": int(__import__("time").time())
        })
        log.info(f"Broker response: {result['status']}")
        return {'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
