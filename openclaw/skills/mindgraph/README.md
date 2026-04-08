# MindGraph OpenClaw skill

This folder is versioned with the MindGraph app. It teaches OpenClaw how to call MindGraph’s HTTP API using your account token.

## Install (end users)

```bash
openclaw skills install mindgraph
```

Or copy this folder to the OpenClaw workspace `skills/mindgraph/`.

## Configure

**Fast path:** open **`demo.json`** in this folder — it is a ready-made `skills.entries` block you can merge into your OpenClaw config (e.g. `~/.openclaw/openclaw.json` or your host’s equivalent, such as Tencent WorkBuddy skill settings if the UI accepts JSON). Delete the `_instructions` key after merging.

Minimal shape:

```json
{
  "skills": {
    "entries": {
      "mindgraph": {
        "env": {
          "MINDGRAPH_BASE_URL": "https://test.mindspringedu.com",
          "MINDGRAPH_ACCOUNT": "138xxxxxxxx",
          "MINDGRAPH_TOKEN": "mgat_..."
        }
      }
    }
  }
}
```

- **MINDGRAPH_BASE_URL**: HTTPS origin of your MindGraph deployment (no trailing slash).
- **MINDGRAPH_ACCOUNT**: Phone number / account login (same as in MindGraph).
- **MINDGRAPH_TOKEN**: Generated in the app under **账户信息 → API Token** (shown once; 7-day validity).

### After you change auth

MindGraph applies new tokens and account checks on **every request**—no wait on the server. If you edit `MINDGRAPH_*` in OpenClaw/WorkBuddy and calls still fail or act like the old token, your **client** may have loaded env only at startup: **save** the config, then **restart** WorkBuddy or OpenClaw (or use a “reload skills / config” action if the product provides one). The next requests will use the new values.

## Publish updates (maintainers)

From the MindGraph repo root:

```bash
npm i -g clawhub
clawhub login
clawhub skill publish ./openclaw/skills/mindgraph --slug mindgraph --name "MindGraph" --version 1.0.0 --tags latest
```

Bump version when `SKILL.md` changes.

**Inline recommendations:** the `start` and `next_batch` HTTP endpoints use **Server-Sent Events (SSE)**, not JSON-only responses. See `SKILL.md` §6.
