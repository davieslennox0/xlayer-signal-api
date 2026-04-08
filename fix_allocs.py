import re

with open("competition_layer.py") as f:
    content = f.read()

old = '    return {s: round(1/len(STRATEGIES), 4) for s in STRATEGIES}'
new = '''    base = round(1/len(STRATEGIES), 4)
    allocs = {s: base for s in STRATEGIES}
    # Fix rounding drift
    last = list(allocs.keys())[-1]
    allocs[last] = round(1 - base * (len(STRATEGIES) - 1), 4)
    return allocs'''

old2 = '    allocs = {s: round(sharpes[s] / total, 4) for s in sharpes}'
new2 = '''    allocs = {s: sharpes[s] / total for s in sharpes}
    # Normalize to exactly 1.0
    total_alloc = sum(allocs.values())
    allocs = {s: round(v / total_alloc, 4) for s, v in allocs.items()}
    last = list(allocs.keys())[-1]
    allocs[last] = round(1 - sum(list(allocs.values())[:-1]), 4)'''

content = content.replace(old, new).replace(old2, new2)

with open("competition_layer.py", "w") as f:
    f.write(content)

print("Done")
