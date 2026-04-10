with open("prime_broker.py") as f:
    content = f.read()

# Persist activity to disk
old = "ACTIVITY_LOG = []"
new = """import json as _json
from pathlib import Path as _Path

_ACTIVITY_FILE = "activity_log.json"

def _load_activity():
    if _Path(_ACTIVITY_FILE).exists():
        try:
            with open(_ACTIVITY_FILE) as f:
                return _json.load(f)
        except:
            pass
    return []

def _save_activity(log):
    with open(_ACTIVITY_FILE, "w") as f:
        _json.dump(log[-100:], f)

ACTIVITY_LOG = _load_activity()"""

old2 = '    return {"activity": ACTIVITY_LOG[-20:]}  # last 20 events'
new2 = '''    return {"activity": ACTIVITY_LOG[-20:]}'''

# Save after every append
old3 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "waiting", "timestamp": int(__import__("time").time())})
        return {"status": "waiting", "reason": "Conditions not met", "asset": asset}'''
new3 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "waiting", "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {"status": "waiting", "reason": "Conditions not met", "asset": asset}'''

old4 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "rejected", "timestamp": int(__import__("time").time())})
        return {"status": "rejected", "reason": risk["reason"]}'''
new4 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": "rejected", "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)
        return {"status": "rejected", "reason": risk["reason"]}'''

old5 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})'''
new5 = '''        ACTIVITY_LOG.append({"agent_id": req.agent_id, "asset": asset, "status": result["status"], "tx_hash": result.get("tx_hash",""), "timestamp": int(__import__("time").time())})
        _save_activity(ACTIVITY_LOG)'''

content = content.replace(old, new).replace(old2, new2).replace(old3, new3).replace(old4, new4).replace(old5, new5)

with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
