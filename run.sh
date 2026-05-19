#!/bin/bash
# NSE Dashboard — One-command launcher
# Usage: bash run.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=/usr/local/bin/python3
STREAMLIT=/Library/Frameworks/Python.framework/Versions/3.14/bin/streamlit

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        NSE Trading Dashboard v1.0            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check if data exists
DATA_DIR="$SCRIPT_DIR/data"
CSV_COUNT=$(ls "$DATA_DIR"/*.csv 2>/dev/null | wc -l | tr -d ' ')

if [ "$CSV_COUNT" -eq "0" ]; then
    echo "⚠️  No data found. Running quick fetch first..."
    echo "   (This takes 2-4 minutes. The delivery screener runs at 7 PM.)"
    echo ""
    "$PYTHON" "$SCRIPT_DIR/fetcher.py" quick
    echo ""
fi

echo "🚀 Starting dashboard at http://localhost:8501"
echo "   Press Ctrl+C to stop."
echo ""

"$STREAMLIT" run "$SCRIPT_DIR/app.py" \
    --server.port 8501 \
    --server.headless false \
    --theme.base dark \
    --theme.primaryColor "#00d4aa" \
    --theme.backgroundColor "#0e1117" \
    --theme.secondaryBackgroundColor "#1a1d27" \
    --theme.textColor "#c0c8d8"
