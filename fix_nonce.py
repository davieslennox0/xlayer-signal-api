with open("execution_agent.py") as f:
    content = f.read()

old = '    nonce = w3.eth.get_transaction_count(WALLET)\n    tx = router.functions.exactInputSingle(params).build_transaction({'
new = '    nonce = w3.eth.get_transaction_count(WALLET, "pending")\n    tx = router.functions.exactInputSingle(params).build_transaction({'

old2 = '    nonce = w3.eth.get_transaction_count(WALLET)\n    tx = token.functions.approve(SWAP_ROUTER, amount_wei).build_transaction({'
new2 = '    nonce = w3.eth.get_transaction_count(WALLET, "pending")\n    tx = token.functions.approve(SWAP_ROUTER, amount_wei).build_transaction({'

content = content.replace(old, new).replace(old2, new2)
with open("execution_agent.py", "w") as f:
    f.write(content)
print("Done")
