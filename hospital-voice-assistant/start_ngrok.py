"""
ngrok Launcher
Starts an ngrok tunnel on port 5000 and automatically updates
NGROK_URL in your .env file so Flask picks it up immediately.

Usage:
    python start_ngrok.py
"""

import subprocess
import time
import requests
import re
import sys
import os


NGROK_API = "http://localhost:4040/api/tunnels"
ENV_FILE = ".env"
FLASK_PORT = 5000


def get_ngrok_url(retries: int = 10, delay: float = 1.5) -> str:
    """Polls the local ngrok API until a public URL is available."""
    for attempt in range(retries):
        try:
            resp = requests.get(NGROK_API, timeout=5)
            tunnels = resp.json().get("tunnels", [])
            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    return tunnel["public_url"]
        except Exception:
            pass
        print(f"  Waiting for ngrok tunnel... ({attempt + 1}/{retries})")
        time.sleep(delay)
    return ""


def update_env(url: str) -> None:
    """Updates or inserts NGROK_URL in the .env file."""
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w") as f:
            f.write(f"NGROK_URL={url}\n")
        return

    with open(ENV_FILE, "r") as f:
        content = f.read()

    if "NGROK_URL=" in content:
        content = re.sub(r"NGROK_URL=.*", f"NGROK_URL={url}", content)
    else:
        content += f"\nNGROK_URL={url}\n"

    with open(ENV_FILE, "w") as f:
        f.write(content)


def main():
    print("▶  Starting ngrok tunnel on port", FLASK_PORT)

    # Launch ngrok as a background process
    proc = subprocess.Popen(
        ["ngrok", "http", str(FLASK_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(2)  # Give ngrok a moment to initialise

    url = get_ngrok_url()
    if not url:
        print("✗  Could not retrieve ngrok URL. Is ngrok installed and authenticated?")
        proc.terminate()
        sys.exit(1)

    update_env(url)

    print(f"✓  ngrok tunnel active: {url}")
    print(f"   Webhook base URL:    {url}/incoming-call")
    print(f"   Health check:        {url}/health")
    print()
    print("  → Set this in your Twilio console:")
    print(f"    Voice webhook URL:  {url}/incoming-call")
    print(f"    Status callback:    {url}/call-status")
    print()
    print("Press Ctrl+C to stop ngrok.\n")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nngrok stopped.")


if __name__ == "__main__":
    main()
