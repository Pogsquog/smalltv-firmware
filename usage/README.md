# AI usage on the clock

Shows today's and this month's Claude Code and GitHub Copilot CLI usage on the
SmallTV, in place of the date. On days with no usage, the date comes back.

```
 PC (WSL)                     Raspberry Pi                 SmallTV
 agent.py  --POST every 5m--> hub.py :8787  <--GET 1/min-- usage.cpp
 reads local transcripts      sums all machines            "CLAUDE  $4.21  $88"
```

- **`agent.py`** runs on each PC you want counted. It reads data that is already
  on disk, so it needs no API keys or GitHub tokens:
  - **Claude Code:** `~/.claude/projects/**/*.jsonl`, and from WSL also
    `/mnt/c/Users/*/.claude/projects`. Each assistant message records its
    tokens. Cost is token counts × the list prices in `PRICES` at the top of
    the script, with cache reads and writes, fast mode and web searches priced
    separately. Each response is counted once, even when it appears on several
    lines or in more than one file.
  - **Copilot CLI:** the `assistant_usage_events` table in
    `~/.copilot/session-store.db`, and from WSL also the Windows copy.
    *Premium requests* are the sum of `request_multiplier` over prompts you
    sent (`initiator` empty or `user`). *AI credits* are the sum of
    `total_nano_aiu` / 1e9.

  Each run sends a full snapshot of every day this month, so a missed or
  repeated run never double counts.
- **`hub.py`** keeps the per-machine daily totals in `usage.json` and serves
  the sums. `GET /api/usage.json` shows the per-machine breakdown.
- **The firmware** polls `USAGE_URL` (set in `secrets.env`) every minute. If
  the hub can't be reached for 30 minutes, the date comes back.

Both scripts use only the Python standard library.

## On the screen

```
              TODAY  MONTH
 CLAUDE       $4.21  $88.4
 COPILOT         12    310
```

`-` means nothing today. Copilot shows premium requests. If the month's ledger
only has AI credits, the row reads `COP CR` and shows credits instead.

## Hub (Raspberry Pi)

Already installed on `stupi2` as the `usage-hub` systemd service, with data in
`~/usage-hub/usage.json`. To update it:

```sh
scp usage/hub.py stupi2:usage-hub/ && ssh stupi2 sudo systemctl restart usage-hub
```

To remove a machine's data: `curl -X DELETE http://192.168.1.105:8787/api/machine/<name>`.

## Agent (each PC to count)

From WSL, with this repo checked out:

```sh
cd usage
python3 agent.py --dry-run                 # check what it finds; prints, sends nothing
```

The dry run lists the transcript folders and Copilot databases it found, which
`initiator` values the Copilot ledger uses, and any models with no price. Then
install it as a systemd user service. This needs systemd in WSL (on by default
in current WSL; check with `systemctl --user status`):

```sh
mkdir -p ~/.local/share/usage-agent ~/.config/systemd/user
cp agent.py ~/.local/share/usage-agent/
cp usage-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now usage-agent
journalctl --user -u usage-agent -f        # "sent N days" every 5 min with -v
```

It sends while WSL is running, and since the agent reads the Windows-side data
too, Windows-only sessions are picked up the next time WSL is up.

Options: `--machine NAME` (default: the hostname), `--claude-dir` and
`--copilot-db` to override discovery, and `--hub`. To require a shared secret,
set `USAGE_TOKEN` in both the hub's and the agent's environment.

## Caveats

- Claude cost is at list prices. It's what an API key pays without a
  negotiated discount, and only an estimate for subscription use. Update
  `PRICES` when prices change. The agent warns about models it has no price for.
- The Copilot ledger schema comes from the CLI's own database, and the work
  PC is the first place it will run against real data. Check `--dry-run` there.
