#!/usr/bin/env bash

set -e

echo "🚀 Starting Hermes Forge stack..."

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/venv"
APP_FILE="telegram_ui.py"
PORT=8000

# ---------------------------
# 🔐 Load .env
# ---------------------------
if [ -f ".env" ]; then
    echo "🔐 Loading .env..."
    export $(grep -v '^#' .env | xargs)
fi

# ---------------------------
# 🧠 Ensure Python
# ---------------------------
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found."
    exit 1
fi

# ---------------------------
# 🧠 Create venv
# ---------------------------
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# ---------------------------
# 📦 Install deps
# ---------------------------
echo "📦 Installing dependencies..."
pip install --upgrade pip >/dev/null
pip install python-telegram-bot playwright requests python-dotenv >/dev/null

python -m playwright install chromium >/dev/null 2>&1 || true

# ---------------------------
# 🧹 Kill old processes
# ---------------------------
pkill -f "http.server" || true
pkill -f "cloudflared" || true
pkill -f "$APP_FILE" || true

# ---------------------------
# 🌐 Start HTTP server
# ---------------------------
echo "🌐 Starting HTTP server..."
python -m http.server $PORT > server.log 2>&1 &
SERVER_PID=$!

sleep 2

# ---------------------------
# 🔐 Ensure cloudflared
# ---------------------------
if [ ! -f "./cloudflared-linux-amd64" ]; then
    echo "📥 Downloading Cloudflare tunnel..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x cloudflared-linux-amd64
fi

# ---------------------------
# 🔐 Start tunnel
# ---------------------------
echo "🔐 Starting Cloudflare tunnel..."
./cloudflared-linux-amd64 tunnel --url http://localhost:$PORT > tunnel.log 2>&1 &
TUNNEL_PID=$!

# ---------------------------
# ⏳ Wait for URL
# ---------------------------
echo "⏳ Waiting for tunnel URL..."

URL=""
for i in {1..25}; do
    sleep 1
    URL=$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' tunnel.log | head -n 1 || true)
    if [ ! -z "$URL" ]; then
        break
    fi
done

if [ -z "$URL" ]; then
    echo "❌ Failed to get tunnel URL"
    kill $SERVER_PID $TUNNEL_PID || true
    exit 1
fi

echo "🌍 Tunnel URL: $URL"

# ---------------------------
# 🔥 EXPORT ENV (NEW WAY)
# ---------------------------
export APP_URL_BASE="$URL"

# also write to runtime file (for dotenv)
echo "APP_URL_BASE=$URL" > .runtime_env

FULL_URL="$URL/outputs/app.html"

# ---------------------------
# 🤖 Start Telegram bot
# ---------------------------
echo "🤖 Starting Telegram bot..."
python "$APP_FILE" &
BOT_PID=$!

echo "✅ Stack is live!"
echo "👉 Web App: $FULL_URL"

# ---------------------------
# 🛑 Cleanup
# ---------------------------
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $SERVER_PID $TUNNEL_PID $BOT_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

wait $BOT_PID
