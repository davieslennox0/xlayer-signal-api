with open("prime_broker.py") as f:
    content = f.read()

old = '''    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()
    log.info("Trade monitor started as background thread")'''

new = '''    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()
    log.info("Trade monitor started as background thread")
    t2 = threading.Thread(target=run_moltbook_heartbeat, daemon=True)
    t2.start()
    log.info("Moltbook heartbeat started")'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
