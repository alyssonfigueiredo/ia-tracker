#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
[ -f .env ] && source .env

python main.py >> tracker.log 2>&1
