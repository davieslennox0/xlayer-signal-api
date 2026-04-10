with open("prime_broker.py") as f:
    content = f.read()

old = '''def verify_x402_payment(tx_hash: str, expected_usdt: float) -> bool:
    """Verify that tx_hash is a valid USDT0 transfer to broker wallet."""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)'''

new = '''def verify_x402_payment(tx_hash: str, expected_usdt: float) -> bool:
    """Verify that tx_hash is a valid USDT0 transfer to broker wallet."""
    try:
        import time
        # Wait for confirmation
        for _ in range(10):
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                break
            time.sleep(2)
        if not receipt:
            return False
        receipt = w3.eth.get_transaction_receipt(tx_hash)'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
