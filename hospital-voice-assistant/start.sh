#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  start.sh  — Launch ngrok + Flask in the correct order
#  Usage:  bash start.sh
# ─────────────────────────────────────────────────────────────

set -e

echo ""
echo "═══════════════════════════════════════════"
echo "   Hospital AI Voice Assistant — Startup   "
echo "═══════════════════════════════════════════"
echo ""

# 1. Activate virtual env if present (Linux/macOS or Windows Git Bash)
if [ -f "venv/bin/activate" ]; then
  echo "▶  Activating virtual environment..."
  source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
  echo "▶  Activating virtual environment..."
  source venv/Scripts/activate
fi

# 2. Ensure data & logs dirs exist
mkdir -p data logs

# 3. Start ngrok in background and update .env
echo "▶  Starting ngrok..."
python start_ngrok.py &
NGROK_PID=$!

# Give ngrok launcher time to update .env
sleep 5

# 4. Flask reads the updated .env (including NGROK_URL) itself via python-dotenv

echo ""
echo "▶  Starting Flask server on port 5000..."
echo ""

# 5. Run Flask
python app.py

# Cleanup
kill $NGROK_PID 2>/dev/null || true
