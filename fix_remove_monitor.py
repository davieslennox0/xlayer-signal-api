with open("demo_agents.py") as f:
    content = f.read()

content = content.replace(
    "from trade_monitor import check_trades, register_trade\n", ""
).replace(
    """            if monitor_counter % 3 == 0:  # check trades every 3 min
                try:
                    check_trades()
                except Exception as e:
                    pass\n""", ""
).replace(
    "            monitor_counter += 1\n", ""
).replace(
    "        monitor_counter = 0\n", ""
)

with open("demo_agents.py", "w") as f:
    f.write(content)
print("Done")
