with open("demo_agents.py") as f:
    content = f.read()

old = 'w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))'
new = '''for rpc in [os.getenv("RPC_URL"), "https://rpc.xlayer.tech", "https://xlayerrpc.okx.com"]:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
        if w3.is_connected():
            break
    except Exception:
        continue'''

content = content.replace(old, new)
with open("demo_agents.py", "w") as f:
    f.write(content)
print("Done")
