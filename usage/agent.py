#!/usr/bin/env python3
"""AI usage agent: totals this month's Claude Code and GitHub Copilot CLI usage
per day on this PC and pushes them to hub.py.

Standard library only. Works in WSL (reads both the WSL and the Windows-side
data under /mnt/c/Users) and on native Windows or Linux.

  python3 agent.py --hub http://192.168.1.105:8787 --dry-run   # print, don't send
  python3 agent.py --hub http://192.168.1.105:8787             # send once
  python3 agent.py --hub http://192.168.1.105:8787 --loop 300  # send every 5 min

Claude Code: every assistant message in ~/.claude/projects/**/*.jsonl carries
its token usage. The cost is computed from the PRICES table below at API list
prices, which is what an API key is billed (before any negotiated discount).

Copilot CLI: each model call is a row in ~/.copilot/session-store.db, table
assistant_usage_events, with the premium-request multiplier and AI credits.
"""
import argparse
import glob
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timezone

# ---- Claude prices, USD per million tokens: (input, output, cache read) -----
# Cache writes cost 1.25x input (5 minute TTL) or 2x input (1 hour TTL).
# Matched by longest prefix of the model id. Update when prices change:
# https://platform.claude.com/docs/en/about-claude/pricing
PRICES = {
    "claude-fable-5-2":  (8.00, 40.00, 0.20),
    "claude-mythos-5-2": (8.00, 40.00, 0.20),
    "claude-fable-5":    (10.00, 50.00, 1.00),   # 5 and 5.1
    "claude-mythos-5":   (10.00, 50.00, 1.00),
    "claude-opus-5-5":   (4.00, 20.00, 0.20),
    "claude-opus-5":     (5.00, 25.00, 0.50),
    "claude-opus-4-8":   (5.00, 25.00, 0.50),
    "claude-opus-4-7":   (5.00, 25.00, 0.50),
    "claude-opus-4-6":   (5.00, 25.00, 0.50),
    "claude-opus-4-5":   (5.00, 25.00, 0.50),
    "claude-opus-4":     (15.00, 75.00, 1.50),   # 4 and 4.1
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5":   (2.00, 10.00, 0.20),
    "claude-sonnet-4":   (3.00, 15.00, 0.30),    # 4, 4.5, 4.6
    "claude-haiku-5-5":  (0.10, 0.50, 0.01),
    "claude-haiku-4-5":  (1.00, 5.00, 0.10),
    "claude-3-5-haiku":  (0.80, 4.00, 0.08),
}
# Fast mode bills at a multiple of the standard rate.
FAST_MULTIPLIER = 2.0
WEB_SEARCH_USD = 0.01   # per search ($10 / 1000)


def price_for(model):
    best = None
    for prefix in PRICES:
        if model.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    return PRICES[best] if best else None


def local_day(ts):
    """ISO timestamp (UTC, 'Z' or offset or naive-UTC) -> local YYYY-MM-DD."""
    ts = ts.strip().replace(" ", "T")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date().isoformat()


# ---- Claude Code transcripts --------------------------------------------------

class ClaudeScanner:
    """Reads transcripts incrementally: they are append-only, so on each pass
    only the bytes added since the last pass are parsed."""

    def __init__(self, roots):
        self.roots = roots
        self.files = {}     # path -> (inode/size key, offset)
        self.msgs = {}      # message key -> (day, usd, output_tokens)
        self.unknown = set()

    def scan(self, since_epoch):
        for root in self.roots:
            for path in glob.iglob(os.path.join(root, "**", "*.jsonl"), recursive=True):
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if st.st_mtime < since_epoch:
                    continue
                prev = self.files.get(path)
                offset = prev[1] if prev and prev[0] == st.st_ino and st.st_size >= prev[1] else 0
                if offset == st.st_size:
                    continue
                try:
                    with open(path, "rb") as f:
                        f.seek(offset)
                        data = f.read()
                except OSError:
                    continue
                # Leave a partly written last line for the next pass.
                end = data.rfind(b"\n") + 1
                for line in data[:end].splitlines():
                    if b'"usage"' in line:
                        self._line(line)
                self.files[path] = (st.st_ino, offset + end)

    def _line(self, raw):
        try:
            e = json.loads(raw)
            msg = e["message"]
            u = msg["usage"]
            model = msg.get("model") or ""
            day = local_day(e["timestamp"])
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        if e.get("type") != "assistant" or not model or model.startswith("<"):
            return
        p = price_for(model)
        if p is None:
            self.unknown.add(model)
            return
        pin, pout, pread = p
        cc = u.get("cache_creation") or {}
        w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
        w5m = (u.get("cache_creation_input_tokens", 0) or 0) - w1h
        usd = ((u.get("input_tokens", 0) or 0) * pin
               + (u.get("output_tokens", 0) or 0) * pout
               + (u.get("cache_read_input_tokens", 0) or 0) * pread
               + max(w5m, 0) * pin * 1.25
               + w1h * pin * 2.0) / 1e6
        if u.get("speed") == "fast":
            usd *= FAST_MULTIPLIER
        stu = u.get("server_tool_use") or {}
        usd += (stu.get("web_search_requests", 0) or 0) * WEB_SEARCH_USD
        # One API response is written as several lines (one per content block),
        # each repeating the usage, and resumed sessions copy old lines into new
        # files. Count each response once, keeping its final (largest) usage.
        key = msg.get("id") or e.get("requestId") or e.get("uuid")
        out = u.get("output_tokens", 0) or 0
        old = self.msgs.get(key)
        if old is None or out >= old[2]:
            self.msgs[key] = (day, usd, out)

    def by_day(self, month):
        days = {}
        for day, usd, _ in self.msgs.values():
            if day.startswith(month):
                days[day] = days.get(day, 0.0) + usd
        return days


# ---- Copilot CLI ledger -------------------------------------------------------

def copilot_by_day(db_paths, month, verbose=False):
    req, credits = {}, {}
    initiators = {}
    for db in db_paths:
        # Copy the database (and its WAL) so the live CLI is never locked, and
        # because SQLite locking doesn't work over WSL's /mnt/c.
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "s.db")
            try:
                shutil.copyfile(db, dst)
                if os.path.exists(db + "-wal"):
                    shutil.copyfile(db + "-wal", dst + "-wal")
                con = sqlite3.connect(dst)
                rows = con.execute(
                    "SELECT created_at, initiator, request_multiplier, total_nano_aiu "
                    "FROM assistant_usage_events WHERE created_at >= ?",
                    (month + "-01",)).fetchall()   # UTC; a few hours' slack is filtered below
                con.close()
            except (OSError, sqlite3.Error) as ex:
                if verbose:
                    print(f"copilot: skipping {db}: {ex}", file=sys.stderr)
                continue
        for created, initiator, mult, nano in rows:
            try:
                day = local_day(created)
            except (ValueError, AttributeError):
                continue
            if not day.startswith(month):
                continue
            initiators[initiator] = initiators.get(initiator, 0) + 1
            # A premium request is charged per prompt you send; the follow-up
            # calls the agent makes on its own are not.
            if initiator in (None, "", "user"):
                req[day] = req.get(day, 0.0) + (mult or 0)
            credits[day] = credits.get(day, 0.0) + (nano or 0) / 1e9
    if verbose and initiators:
        print(f"copilot: rows by initiator {initiators}", file=sys.stderr)
    return req, credits


# ---- discovery ----------------------------------------------------------------

def default_claude_roots():
    roots = []
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        roots.append(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects"))
    roots.append(os.path.expanduser("~/.claude/projects"))
    roots += glob.glob("/mnt/c/Users/*/.claude/projects")   # Windows side, from WSL
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]


def default_copilot_dbs():
    home = os.environ.get("COPILOT_HOME") or os.path.expanduser("~/.copilot")
    dbs = [os.path.join(home, "session-store.db")]
    dbs += glob.glob("/mnt/c/Users/*/.copilot/session-store.db")
    return [d for d in dict.fromkeys(dbs) if os.path.isfile(d)]


# ---- main ---------------------------------------------------------------------

def build_report(machine, scanner, copilot_dbs, verbose):
    today = date.today()
    month = today.strftime("%Y-%m")
    month_start = time.mktime(today.replace(day=1).timetuple())
    scanner.scan(month_start - 86400)   # a day's slack for time zones
    claude = scanner.by_day(month)
    req, credits = copilot_by_day(copilot_dbs, month, verbose)
    days = {}
    for d in set(claude) | set(req) | set(credits):
        days[d] = {"claude_usd": round(claude.get(d, 0.0), 4),
                   "copilot_req": round(req.get(d, 0.0), 2),
                   "copilot_credits": round(credits.get(d, 0.0), 4)}
    # Always send today, even if zero, so the hub knows the agent is alive.
    days.setdefault(today.isoformat(), {"claude_usd": 0.0, "copilot_req": 0.0, "copilot_credits": 0.0})
    if scanner.unknown:
        print(f"warning: no price for {sorted(scanner.unknown)}; add them to PRICES", file=sys.stderr)
    return {"machine": machine, "days": dict(sorted(days.items()))}


def send(hub, token, report):
    req = urllib.request.Request(hub.rstrip("/") + "/api/report",
                                 data=json.dumps(report).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hub", default=os.environ.get("USAGE_HUB", "http://192.168.1.105:8787"))
    ap.add_argument("--token", default=os.environ.get("USAGE_TOKEN", ""))
    ap.add_argument("--machine", default=socket.gethostname().lower())
    ap.add_argument("--claude-dir", action="append", help="transcript root (repeatable); default: auto")
    ap.add_argument("--copilot-db", action="append", help="session-store.db (repeatable); default: auto")
    ap.add_argument("--loop", type=int, metavar="SECONDS", help="keep running, sending every SECONDS")
    ap.add_argument("--dry-run", action="store_true", help="print the report instead of sending it")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    roots = a.claude_dir or default_claude_roots()
    dbs = a.copilot_db or default_copilot_dbs()
    verbose = a.verbose or a.dry_run
    if verbose:
        print(f"claude roots: {roots}\ncopilot dbs: {dbs}", file=sys.stderr)
    scanner = ClaudeScanner(roots)
    while True:
        report = build_report(a.machine, scanner, dbs, verbose)
        if a.dry_run:
            print(json.dumps(report, indent=1))
            return
        try:
            send(a.hub, a.token, report)
            if verbose:
                print(f"{datetime.now():%H:%M:%S} sent {len(report['days'])} days", file=sys.stderr)
        except OSError as ex:
            print(f"{datetime.now():%H:%M:%S} send failed: {ex}", file=sys.stderr)
            if not a.loop:
                sys.exit(1)
        if not a.loop:
            return
        time.sleep(a.loop)


if __name__ == "__main__":
    main()
