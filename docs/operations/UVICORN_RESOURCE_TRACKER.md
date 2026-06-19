# Uvicorn multi-worker and `resource_tracker` warnings

## Symptom

Logs may show:

```text
multiprocessing/resource_tracker.py:170: UserWarning: resource_tracker: process died unexpectedly, relaunching.  Some resources might leak.
```

Often immediately after Uvicorn logs such as:

```text
[SRVR] Received SIGHUP, restarting processes.
```

## Root cause (what is actually happening)

1. **Uvicorn’s multiprocessing supervisor** (parent process) can **reload worker processes** when it receives **SIGHUP**.
2. Worker processes are stopped and replaced as part of that reload.
3. Python’s stdlib **`multiprocessing.resource_tracker`** may treat those exits as “unexpected” and emit the **UserWarning**, even when the shutdown was orchestrated by Uvicorn.

This is **not** specific to MindBot routing or application business logic; it is the interaction of **Uvicorn’s worker lifecycle** and **Python’s resource tracker** (notably visible on **Python 3.13** in many deployments).

## What to check on the server (“who sent SIGHUP?”)

The repository cannot see your production signals. Inspect how the process is supervised:

| Source | What to look for |
|--------|------------------|
| **systemd** | Unit file: `ExecReload=`, `KillSignal=`, or wrappers that run `kill -HUP` on the Uvicorn **parent** PID. Default `systemctl reload` only works if `ExecReload` is set. |
| **Supervisor / PM2 / Docker** | Reload hooks, `kill -HUP`, or “graceful reload” features aimed at the app master process. |
| **Operators / scripts** | Manual `kill -HUP <pid>`, deploy scripts, or cron jobs that signal the server to “refresh” workers. |
| **Hosting** | Platform-specific reload that maps to SIGHUP. |

**In-repo reference:** [`scripts/setup/mindgraph.service.template`](../../scripts/setup/mindgraph.service.template) ships **without** `ExecReload`, uses **`KillSignal=SIGTERM`** for stop/restart, and **`ExecStart=… main.py`** — so a stock install from that template does **not** encourage `systemctl reload` unless you add `ExecReload` yourself.

**In-repo scripts:** [`scripts/utils/clear_pycache.sh`](../../scripts/utils/clear_pycache.sh) uses **`systemctl restart mindgraph`** (or equivalent), not `reload`.

## Recommended policy

1. **Prefer full restart for deployments** (e.g. `systemctl restart mindgraph` or your orchestrator’s equivalent) instead of signaling **SIGHUP** to reload only Uvicorn workers, **unless** you explicitly rely on HUP-based worker refresh and accept the warning noise.
2. **Do not add** `ExecReload=kill -HUP $MAINPID` (or similar) to the MindGraph systemd unit **for routine deploys** if you want to avoid this warning and reduce ambiguous multiprocessing cleanup.
3. If you **must** use HUP reloads (e.g. long-lived parent, quick worker swap), treat the message as **often benign** unless you observe real leaks (growing fds, runaway semaphores, OOM). Consider tracking **CPython fixes** for `resource_tracker` on your exact **3.13.x** patch level.

## Unrelated log lines

Do **not** confuse this with:

- **`[TokenBuffer] Redis stream read failed`** — Redis/client issue, not `resource_tracker`.
- **Database pool vs `max_connections` warnings** — Postgres sizing; unrelated.

## Summary

| Question | Answer |
|----------|--------|
| Is MindGraph “broken”? | No — this is **supervisor signal + stdlib multiprocessing** behavior. |
| What triggers it? | Often **SIGHUP → Uvicorn worker restart**. |
| What should we do? | **Find who sends SIGHUP** in prod; **prefer `restart`** over HUP reload for predictable shutdown; optionally **ignore** the warning if HUP reloads are intentional and the app stays healthy. |
