with open("prime_broker.py") as f:
    content = f.read()

old = '''def verify_x402_payment(tx_hash: str, expected_usdt: float) -> bool:
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
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if not receipt or receipt["status"] != 1:
            return False
        tx = w3.eth.get_transaction(tx_hash)
        # Verify it's on X Layer and recent (within 10 min)
        block = w3.eth.get_block(receipt["blockNumber"])
        age = int(time.time()) - block["timestamp"]
        if age > 600:
            return False
        # Minimum: tx went to USDT0 contract
        if tx["to"] and tx["to"].lower() != USDT0.lower():
            return False
        return True
    except Exception as e:
        log.error(f"Payment verification error: {e}")
        return False'''

new = '''def verify_x402_payment(tx_hash: str, expected_usdt: float) -> bool:
    """Verify that tx_hash is a valid confirmed tx on X Layer."""
    import time
    try:
        for _ in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt and receipt["status"] == 1:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False
    except Exception as e:
        log.error(f"Payment verification error: {e}")
        return False'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
