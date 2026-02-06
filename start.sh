#!/bin/bash

echo "🚀 Starting Alpha Bot v2.0..."

# Check if PORT is set
if [ -z "$PORT" ]; then
    export PORT=8080
fi

echo "Using PORT: $PORT"

# Start main bot (Flask runs inside main.py now)
python main.py
