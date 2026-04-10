with open("prime_broker.py") as f:
    content = f.read()

old = '''FEE_TIERS = {
    "signal":    {"price_usdt": 0.01, "splits": {"scout": 0.6, "risk": 0.4}},
    "validate":  {"price_usdt": 0.02, "splits": {"risk": 0.7, "learning": 0.3}},
    "execute":   {"price_usdt": 0.05, "splits": {"risk": 0.3, "learning": 0.3, "execution": 0.4}},
    "full":      {"price_usdt": 0.10, "splits": {"scout": 0.25, "risk": 0.25, "learning": 0.25, "execution": 0.25}},
}'''

new = '''FEE_TIERS = {
    "signal":    {"price_usdt": 0.01, "splits": {"scout": 0.6, "risk": 0.4}},
    "validate":  {"price_usdt": 0.02, "splits": {"risk": 0.7, "learning": 0.3}},
    "execute":   {"price_usdt": 0.05, "splits": {"risk": 0.3, "learning": 0.3, "execution": 0.4}},
    "full":      {"price_usdt": 0.02, "splits": {"scout": 0.25, "risk": 0.25, "learning": 0.25, "execution": 0.25}},
}'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
