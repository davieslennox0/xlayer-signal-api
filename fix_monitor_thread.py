with open("prime_broker.py") as f:
    content = f.read()

old = '''if __name__ == "__main__":
    import uvicorn
    uvicorn.run("prime_broker:app", host="0.0.0.0", port=8000, reload=False)'''

new = '''def run_monitor():
    import time
    from trade_monitor import check_trades
    while True:
        try:
            check_trades()
        except Exception as e:
            log.error(f"Monitor error: {e}")
        time.sleep(180)

@app.on_event("startup")
async def startup():
    import threading
    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()
    log.info("Trade monitor started as background thread")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("prime_broker:app", host="0.0.0.0", port=8000, reload=False)'''

content = content.replace(old, new)
with open("prime_broker.py", "w") as f:
    f.write(content)
print("Done")
