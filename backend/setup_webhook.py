# backend/setup_webhook.py
# Run this ONCE after starting ngrok to register the Telegram webhook.
#
# Usage (from backend/ directory):
#   python setup_webhook.py https://abc123.ngrok-free.app
#
# Or run without args and it will prompt for the URL.

import os
import sys
import pathlib
import requests

from dotenv import load_dotenv

_backend_env = pathlib.Path(__file__).parent / ".env"
_root_env    = pathlib.Path(__file__).parent.parent / ".env"

if _backend_env.exists():
    load_dotenv(_backend_env)
    print(f"Loaded env from: {_backend_env}")
elif _root_env.exists():
    load_dotenv(_root_env)
    print(f"Loaded env from: {_root_env}")
else:
    print("WARNING: No .env file found. Make sure TELEGRAM_BOT_TOKEN is set.")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

if not TOKEN or TOKEN == "PASTE_YOUR_NEW_TOKEN_HERE":
    print("\nERROR: TELEGRAM_BOT_TOKEN is missing or still a placeholder.")
    print("  -> Open .env and set TELEGRAM_BOT_TOKEN=<your token from BotFather>")
    sys.exit(1)

print(f"Token loaded (ends in ...{TOKEN[-6:]})")

# Accept URL from CLI arg or prompt
if len(sys.argv) > 1:
    PUBLIC_URL = sys.argv[1].rstrip("/")
else:
    PUBLIC_URL = input("\nEnter your ngrok HTTPS URL (e.g. https://abc123.ngrok-free.app): ").strip().rstrip("/")

if not PUBLIC_URL.startswith("https://"):
    print("ERROR: URL must start with https:// — Telegram requires HTTPS")
    sys.exit(1)

WEBHOOK_URL = f"{PUBLIC_URL}/api/telegram/webhook"
print(f"\nRegistering webhook -> {WEBHOOK_URL}\n")

# Step 1: Delete any old webhook first
delete_res = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/deleteWebhook",
    json={"drop_pending_updates": True},
    timeout=10,
)
print("deleteWebhook:", delete_res.json())

# Step 2: Register new webhook
set_res = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    },
    timeout=10,
)
result = set_res.json()
ok = result.get("ok", False)
print(f"{'OK' if ok else 'FAILED'} setWebhook:", result)

if not ok:
    print("\nCommon causes:")
    print("  * Token is wrong/revoked -- get a new one from @BotFather")
    print("  * ngrok URL is not HTTPS")
    print("  * Backend is not running on port 8000")
    sys.exit(1)

# Step 3: Verify
info = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo",
    timeout=10,
).json()

print("\nWebhook info:")
if info.get("ok"):
    wh = info.get("result", {})
    print(f"  URL:            {wh.get('url', 'not set')}")
    print(f"  Pending updates:{wh.get('pending_update_count', 0)}")
    print(f"  Last error:     {wh.get('last_error_message', 'none')}")
else:
    print("  ", info)

print("\nDone! Send a message to @msme_gst_bot to test.")
