with open("risk_agent.py") as f:
    content = f.read()

old = '    if position_size < 0.1:\n        position_size = 0.5  # minimum viable demo size'
new = '    if position_size < 0.1:\n        position_size = 1.0  # minimum viable demo size'

content = content.replace(old, new)
with open("risk_agent.py", "w") as f:
    f.write(content)
print("Done")
