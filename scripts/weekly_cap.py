#!/usr/bin/env python3
"""Weekly cap spread over the days of the week, so a Monday cannot eat half the week.

The share left to autonomous sessions is `100 - reserve` percent of the weekly quota (the
rest is yours for working by hand). That share is spread over 7 days, plus a `margin` of
points for a busier day. The weekly percentage and its renewal time are the ones `/usage`
shows in Claude Code, read with the login `claude` already keeps (`.credentials.json` in the
config dir, or the macOS keychain). The token is only sent to that endpoint: never printed
or stored. `--pct` and `--renews` override the reading.

Usage: weekly_cap.py [--pct 42 --renews 2026-10-11T18:00:00+00:00] [--now ISO] [--reserve 15] [--margin 5]
Exit 0 if there is room to launch, 1 (with the reason on stdout) if the cap is reached,
2 if the usage could not be read.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

RESERVE = 15
MARGIN = 5
URL = "https://api.anthropic.com/api/oauth/usage"
KEYCHAIN_SERVICE = "Claude Code-credentials"
UNREADABLE = ("quota: could not read the weekly usage (log in with `claude`, "
              "or pass --pct and --renews)")


def credentials_path():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, ".credentials.json")


def _keychain():
    """The login JSON on macOS, where `claude` keeps it in the keychain; None elsewhere."""
    if sys.platform != "darwin":
        return None
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _token(raw):
    try:
        return json.loads(raw)["claudeAiOauth"]["accessToken"]
    except (ValueError, KeyError, TypeError):
        return None


def _login_token(credentials, keychain):
    try:
        with open(credentials or credentials_path(), encoding="utf-8") as f:
            token = _token(f.read())
    except OSError:
        token = None
    return token or _token(keychain())


def read_usage(opener=None, credentials=None, keychain=_keychain):
    """`{"seven_day": (pct, renews_iso)}` as `/usage` shows it, or None if it cannot be
    read (no login, no network, unexpected reply)."""
    token = _login_token(credentials, keychain)
    if not token:
        return None
    req = urllib.request.Request(URL, headers={
        "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    week = data.get("seven_day") if isinstance(data, dict) else None
    if not isinstance(week, dict) or week.get("utilization") is None or not week.get("resets_at"):
        return None
    return {"seven_day": (float(week["utilization"]), week["resets_at"])}


def _utc(iso):
    t = dt.datetime.fromisoformat(iso)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _minute(t):
    """To the nearest minute: the endpoint's renewal time jitters by a second around it."""
    return (t + dt.timedelta(seconds=30)).replace(second=0, microsecond=0)


def cap_today(renews, now, reserve=RESERVE, margin=MARGIN):
    """(cap %, when it rises) for the day in progress of the week that renews at `renews`."""
    renews = renews if isinstance(renews, dt.datetime) else _utc(renews)
    start = renews - dt.timedelta(days=7)
    day = min(max((now - start) // dt.timedelta(days=1) + 1, 1), 7)
    cap = min((100 - reserve) * day / 7 + margin, 100 - reserve)
    return cap, start + dt.timedelta(days=day)


def pause_reason(usage, now=None, reserve=RESERVE, margin=MARGIN):
    """Why nothing should be launched, or None. `usage`: {"seven_day": (pct, renews_iso)}."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if "seven_day" not in usage or not usage["seven_day"][1]:
        return None
    pct, renews = usage["seven_day"]
    cap, rises = cap_today(renews, now, reserve, margin)
    if pct >= cap:
        return (f"quota: the week is at {pct:.0f} % and today's cap is {cap:.0f} % "
                f"(the week spread by days); resuming {_minute(rises):%Y-%m-%d %H:%M} UTC")
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pct", type=float)
    p.add_argument("--renews")
    p.add_argument("--now")
    p.add_argument("--reserve", type=float, default=RESERVE)
    p.add_argument("--margin", type=float, default=MARGIN)
    a = p.parse_args(argv)
    if (a.pct is None) != (a.renews is None):
        p.error("--pct and --renews go together")
    usage = {"seven_day": (a.pct, a.renews)} if a.pct is not None else read_usage()
    if not usage:
        print(UNREADABLE)
        return 2
    now = _utc(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    reason = pause_reason(usage, now, a.reserve, a.margin)
    if reason:
        print(reason)
        return 1
    pct, renews = usage["seven_day"]
    cap, _ = cap_today(renews, now, a.reserve, a.margin)
    print(f"quota: the week is at {pct:.0f} %, today's cap is {cap:.0f} %; "
          f"it renews {_minute(_utc(renews)):%Y-%m-%d %H:%M} UTC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
