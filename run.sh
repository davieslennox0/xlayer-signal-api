#!/data/data/com.termux/files/usr/bin/bash
cd ~/myriad
while true; do
    echo "Starting bot..."
    python -u bot.py
    echo "Bot stopped — restarting in 10 seconds..."
    sleep 10
done
