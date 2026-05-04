# Workshop collab load tests (Locust)

Pre-deploy / staging soak for **`/api/ws/canvas-collab/{code}`** using real WebSockets.

## Targets

Typical sizing from production-hardening plan:

- Five rooms × **100 editors** (~join + pings + light updates spread by Locust weights).
- One larger room × **500 editors** (join storm pressure + fan-out hot path).

`WORKSHOP_SIZES` defaults to **`5x100,1x500`**; you **must supply one workshop code per logical room**.

## Prerequisites

```bash
pip install locust websocket-client
```

Staging or load env must expose:

- JWT session (`?token=`) authorised for every listed workshop code **or** rely on **`access_token` cookie compatibility** paths (JWT still required serverside).
- Network path from runner → deployment for `ws`/`wss`.

## Primary environment variables

| Variable | Meaning |
| --- | --- |
| **`COLLAB_LOCUST_HOST`** | Base **`https://…`** deployment URL (**not** WS). Scheme maps to **`wss://`**. Example: `https://staging.mindgraph.local`. |
| **`COLLAB_JWT`** | Access token appended as **`?token=…`** (same heuristic as browsers / `extract_bearer_token_from_websocket`). |
| **`COLLAB_CODES`** | Comma-separated presentation codes aligned with **`WORKSHOP_SIZES`**. For defaults you need exactly **six codes** (`5 + 1` rooms). |
| **`WORKSHOP_SIZES`** | Overrides default `5x100,1x500`. Grammar: `NxM` segments comma-separated (`N` logical rooms cloned from the next **`N`** codes, each weighted by **`M`** for Locust `weight`). |

Optional:

- Tune Locust swarm size / spawn rate externally (`locust … -u -r`).
- Narrow room mix by shrinking **`WORKSHOP_SIZES`** + matching shorter **`COLLAB_CODES`**.

## Minimal example

```powershell
cd loadtests/collab
 $env:COLLAB_LOCUST_HOST="https://staging.example.com"
 $env:COLLAB_JWT="<JWT>"
 # six codes aligned with WORKSHOP_SIZES default 5x100 + 1x500
 $env:COLLAB_CODES="A1AAA,B2BBB,C3CCC,D4DDD,E5EEE,F6BIG"
locust -f locustfile.py --headless -u 500 -r 20 -t 5m --tags collab
```

> Use `--tags`/`--exclude-tags` to partition scenarios if extended.

## Operational thresholds

| Scenario | Guideline |
| --- | --- |
| p95 handshake + first `joined`/`snapshot` | < 3s on stable staging |
| Abnormal closures (anything except benign **4003** duplicate tab churn) | < 0.5% sustained |
| Redis `CLIENT PAUSE`/outage rehearsal | Brief PG NOTIFY fan-out path should converge without permanent backlog (watch Prometheus `record_ws_fanout_*` gauges) |

Tune shard concurrency (**`WORKSHOP_FANOUT_SHARD_CONCURRENCY`**) separately if broadcaster CPU spikes.

## Troubleshooting checklist

| Symptom | Check |
| --- | --- |
| Mass **`1008` join rate limits** during soak | Stagger ramps or mint **`resume_token`** from browsers for reconnect-only paths; widen limits only deliberately. |
| PG NOTIFY **`payload too large`** warnings | Fallback path rejecting frames—restore Redis availability; audits should not persist entire payload only for oversize notifies. |
| TLS / mixed-content blocks | Guarantee **HTTPS staging** ⇒ **`wss://`** derivation from `http_base_to_ws_base`. |

## CI / nightly

GitHub **`nightly-collab.yml`** (manual `workflow_dispatch` by default) can run the Locust CLI when you supply HTTPS base URL, JWT & codes secrets/inputs against a reachable deployment.
