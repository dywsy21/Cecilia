#!/bin/zsh
# Deploy script for Cecilia bot
# Ensure the script is run from the project root
cd "$(dirname "$0")" || exit 1
source venv/bin/activate
python3 main.py
