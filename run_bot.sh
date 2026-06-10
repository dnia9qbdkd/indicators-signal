#!/bin/bash

# Run the trading signal bot and capture output
python signal_bot.py > signal_bot_output.txt 2>&1

echo "Bot execution completed. Output saved to signal_bot_output.txt"
