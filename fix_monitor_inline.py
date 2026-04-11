with open("demo_agents.py") as f:
    content = f.read()

old = '''import os
import time
import json
import logging
import requests
from web3 import Web3
from dotenv import load_dotenv'''

new = '''import os
import time
import json
import logging
import requests
from web3 import Web3
from dotenv import load_dotenv
from trade_monitor import check_trades, register_trade'''

old2 = '''    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\\nAgents stopped")'''

new2 = '''    try:
        monitor_counter = 0
        while True:
            time.sleep(60)
            monitor_counter += 1
            if monitor_counter % 3 == 0:  # check trades every 3 min
                try:
                    check_trades()
                except Exception as e:
                    pass
    except KeyboardInterrupt:
        print("\\nAgents stopped")'''

content = content.replace(old, new).replace(old2, new2)
with open("demo_agents.py", "w") as f:
    f.write(content)
print("Done")
