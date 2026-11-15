#!/usr/bin/env python3
"""Fetch Yahoo Finance predefined screeners and write static JSON for the site.

Runs in GitHub Actions on a schedule; the browser reads the committed JSON
files instead of hitting CORS-blocked Yahoo endpoints through flaky proxies.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEEDS = {
    "gainers": ["DAY_GAINERS", "day_gainers"],
    "losers": ["DAY_LOSERS", "day_losers"],
    "active": ["MOST_ACTIVES", "most_actives"],
}

COUNT = 50
OUT_DIR = Path(__file__).resolve().parent.parent / "data"
YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_quotes(scr_id: str):
    last_error = None
    for host in YAHOO_HOSTS:
        url = (
            f"https://{host}/v1/finance/screener/predefined/saved"
            f"?scrIds={scr_id}&count={COUNT}&fmt=json&lang=en-US&region=US"
        )
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                result = data.get("finance", {}).get("result") or []
                if result and result[0].get("quotes"):
                    return result[0]["quotes"]
                break
            except Exception as exc:  # noqa: BLE001 - retry next host/attempt
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    return None


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    failures = []

    for key, ids in FEEDS.items():
        quotes = None
        for scr_id in ids:
            try:
                quotes = fetch_quotes(scr_id)
            except Exception as exc:  # noqa: BLE001 - report and try next id
                print(f"[{key}] {scr_id} failed: {exc}", file=sys.stderr)
            if quotes:
                break
        if not quotes:
            failures.append(key)
            continue
        out = OUT_DIR / f"screener-{key}.json"
        out.write_text(
            json.dumps({"updated": updated, "quotes": quotes}, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"[{key}] wrote {len(quotes)} quotes -> {out.name}")

    if failures:
        print(f"Failed feeds: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
