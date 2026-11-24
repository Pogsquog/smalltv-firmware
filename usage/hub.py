#!/usr/bin/env python3
"""AI usage hub: collects daily usage totals pushed by agent.py on each PC and
serves the sums for today and this month to the SmallTV.

Standard library only. Run:  python3 hub.py [--port 8787] [--data usage.json]

  POST /api/report     body from agent.py; replaces that machine's days
  GET  /api/usage.txt  one line for the SmallTV (format below)
  GET  /api/usage.json the same plus a per-machine breakdown, for people
  DELETE /api/machine/<name>  forget a machine's data

If USAGE_TOKEN is set in the environment, reports must send
"Authorization: Bearer <token>". Reads are always open (LAN only).

usage.txt is a single space-separated line, so the ESP8266 can parse it
without a JSON library:

  v1 <today YYYY-MM-DD> <claude_usd_today> <claude_usd_month>
     <copilot_req_today> <copilot_req_month> <copilot_credits_today>
     <copilot_credits_month> <seconds_since_last_report>
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = ("claude_usd", "copilot_req", "copilot_credits")
MAX_BODY = 256 * 1024
KEEP_DAYS = 400   # drop history older than this

lock = threading.Lock()
state = {"machines": {}}   # machine -> {"updated": epoch, "days": {day: {field: value}}}
data_path = None


def load():
    global state
    try:
        with open(data_path, encoding="utf-8") as f:
            state = json.load(f)
        state.setdefault("machines", {})
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        print(f"warning: could not read {data_path}: {e}", file=sys.stderr)


def save():
    tmp = data_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, data_path)


def valid_day(s):
    try:
        date.fromisoformat(s)
        return len(s) == 10
    except (TypeError, ValueError):
        return False


def apply_report(body):
    machine = body.get("machine")
    days = body.get("days")
    if not isinstance(machine, str) or not 0 < len(machine) <= 64 or not isinstance(days, dict):
        raise ValueError("need machine (string) and days (object)")
    clean = {}
    for day, rec in days.items():
        if not valid_day(day) or not isinstance(rec, dict):
            raise ValueError(f"bad day entry {day!r}")
        clean[day] = {k: float(rec.get(k, 0) or 0) for k in FIELDS}
    cutoff = date.fromordinal(date.today().toordinal() - KEEP_DAYS).isoformat()
    with lock:
        m = state["machines"].setdefault(machine, {"days": {}})
        # The agent sends a full snapshot of the days it covers, so each
        # reported day replaces what was stored: re-sending never double counts.
        m["days"].update(clean)
        m["days"] = {d: v for d, v in m["days"].items() if d >= cutoff}
        m["updated"] = time.time()
        save()


def totals():
    today = date.today().isoformat()
    month = today[:7]
    out = {"today": today, "machines": {}}
    sums = {f"{k}_{p}": 0.0 for k in FIELDS for p in ("today", "month")}
    last = 0.0
    with lock:
        for name, m in state["machines"].items():
            per = {f"{k}_{p}": 0.0 for k in FIELDS for p in ("today", "month")}
            for day, rec in m.get("days", {}).items():
                if day[:7] != month:
                    continue
                for k in FIELDS:
                    v = rec.get(k, 0)
                    per[f"{k}_month"] += v
                    if day == today:
                        per[f"{k}_today"] += v
            for k, v in per.items():
                sums[k] += v
            per["updated"] = m.get("updated", 0)
            last = max(last, per["updated"])
            out["machines"][name] = per
    out.update(sums)
    out["age_s"] = int(time.time() - last) if last else -1
    return out


def usage_line(t):
    return "v1 %s %.2f %.2f %.1f %.1f %.2f %.2f %d\n" % (
        t["today"], t["claude_usd_today"], t["claude_usd_month"],
        t["copilot_req_today"], t["copilot_req_month"],
        t["copilot_credits_today"], t["copilot_credits_month"], t["age_s"])


class Handler(BaseHTTPRequestHandler):
    server_version = "usage-hub/1"

    def send(self, code, body, ctype="text/plain; charset=utf-8"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/usage.txt":
            self.send(200, usage_line(totals()))
        elif path in ("/api/usage.json", "/"):
            self.send(200, json.dumps(totals(), indent=1) + "\n", "application/json")
        else:
            self.send(404, "not found\n")

    def authorized(self):
        token = os.environ.get("USAGE_TOKEN")
        return not token or self.headers.get("Authorization") == f"Bearer {token}"

    def do_DELETE(self):
        prefix = "/api/machine/"
        if not self.path.startswith(prefix):
            return self.send(404, "not found\n")
        if not self.authorized():
            return self.send(401, "bad token\n")
        with lock:
            gone = state["machines"].pop(self.path[len(prefix):], None)
            save()
        self.send(200 if gone else 404, "ok\n" if gone else "no such machine\n")

    def do_POST(self):
        if self.path != "/api/report":
            return self.send(404, "not found\n")
        if not self.authorized():
            return self.send(401, "bad token\n")
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= MAX_BODY:
                raise ValueError("bad Content-Length")
            apply_report(json.loads(self.rfile.read(n)))
        except (ValueError, TypeError, AttributeError) as e:
            return self.send(400, f"{e}\n")
        self.send(200, "ok\n")

    def log_message(self, fmt, *args):
        # Only log reports and errors; the SmallTV polls every minute.
        if self.command == "POST" or not str(args[1] if len(args) > 1 else "").startswith("2"):
            super().log_message(fmt, *args)


def main():
    global data_path
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.json"))
    a = ap.parse_args()
    data_path = a.data
    load()
    print(f"usage hub on {a.bind}:{a.port}, data {data_path}", flush=True)
    ThreadingHTTPServer((a.bind, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
