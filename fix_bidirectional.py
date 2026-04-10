with open("demo_agents.py") as f:
    content = f.read()

# Add cycle counter to alternate direction
old = 'def agent_cycle(agent: dict):'
new = '''AGENT_CYCLES = {"Alice": 0, "Bob": 0, "Charlie": 0}

def agent_cycle(agent: dict):
    AGENT_CYCLES[agent["name"]] += 1'''

old2 = '    # Call AlphaLoop broker\n    try:\n        res = requests.post(f"{BROKER_URL}/broker", json={\n            "asset":    asset,\n            "agent_id": agent["name"].lower(),\n            "tx_hash":  tx_hash\n        }, timeout=60)'

new2 = '''    # Alternate direction every cycle for circular trading
    cycle = AGENT_CYCLES[agent["name"]]
    forced_direction = "UP" if cycle % 2 == 0 else "DOWN"

    # Call AlphaLoop broker
    try:
        res = requests.post(f"{BROKER_URL}/execute", json={
            "asset":       asset,
            "direction":   forced_direction,
            "amount_usdt": 0.50,
            "agent_id":    agent["name"].lower(),
            "tx_hash":     tx_hash
        }, timeout=60)'''

content = content.replace(old, new).replace(old2, new2)

# Fix response parsing for /execute endpoint
old3 = '        status = result.get("status", "unknown")\n        log.info(f"Broker response: {status}")\n\n        if status == "success":\n            log.info(f"Trade executed: {result.get(\'explorer\')}")\n        elif status == "waiting":\n            log.info(f"Agent waiting: {result.get(\'reason\')}")\n        else:\n            log.info(f"Rejected: {result.get(\'reason\')}")'

new3 = '''        status = result.get("status", "unknown")
        log.info(f"Response: {status} | direction: {forced_direction}")
        if status == "success":
            log.info(f"Trade executed: {result.get('explorer')}")
        else:
            log.info(f"Not executed: {result.get('reason', result.get('detail', ''))}")'''

content = content.replace(old3, new3)

with open("demo_agents.py", "w") as f:
    f.write(content)
print("Done")
