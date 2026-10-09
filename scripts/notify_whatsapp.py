#!/usr/bin/env python3
"""Send a text through a WhatsApp gateway that exposes `POST /send {recipient, message}`.

URL and recipient come from the environment or a `.env` file outside git:
`WHATSAPP_API_URL` and `WHATSAPP_RECIPIENT`. There is no default URL: a loopback default
points at a machine where the service is not running and fails silently.

Usage: notify_whatsapp.py "text"      (exit 0 only if the gateway confirms the send)
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def config(env_file=ENV, environ=None):
    """(url, recipient). The environment wins over the .env file."""
    environ = os.environ if environ is None else environ
    values = {}
    if Path(env_file).is_file():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    values.update({k: v for k, v in environ.items() if k.startswith("WHATSAPP_")})
    return values.get("WHATSAPP_API_URL", "").rstrip("/"), values.get("WHATSAPP_RECIPIENT", "")


def send(text, url, recipient, opener=urllib.request.urlopen):
    """True only if the gateway confirms the send; without URL or recipient nothing is tried."""
    if not url or not recipient:
        return False
    req = urllib.request.Request(
        f"{url}/send",
        data=json.dumps({"recipient": recipient, "message": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(req, timeout=15) as resp:
            return bool(json.load(resp).get("success"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def main(argv):
    if len(argv) != 2:
        print("usage: notify_whatsapp.py TEXT", file=sys.stderr)
        return 2
    url, recipient = config()
    if not url or not recipient:
        print("WHATSAPP_API_URL and WHATSAPP_RECIPIENT are not set", file=sys.stderr)
        return 1
    return 0 if send(argv[1], url, recipient) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
