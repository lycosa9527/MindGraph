# MindGraph WorkBuddy / OpenClaw skill

This folder is versioned with the MindGraph app. It teaches WorkBuddy (OpenClaw) how to call MindGraph’s HTTP API.

**Agent behavior (`SKILL.md`):** Pick the diagram type, author the semantic `spec`, then save and draw. MindGraph is the pen. Credentials come from **`account.json`** (filled when the user downloads the zip from 账户信息).

## Install (end users)

1. In MindGraph: **账户信息 → WorkBuddy技能包** (downloads a zip).
2. Unzip. **`account.json` and `.env`** already have your phone, `mgat_` token, and server URL.
3. Copy the `mindgraph` folder to WorkBuddy `skills/` (e.g. `%USERPROFILE%\.workbuddy\skills\mindgraph`).
4. Ready — no env UI, no pasting token in chat.

If the user has **no token yet**, download **creates one** and writes it into `account.json`. If they already have a live token, download **reuses** it so the zip matches **账户信息**. Regenerating the token in the account modal invalidates old skill folders and the Chrome extension. Tokens last 90 days.

## Files in this bundle

| File | Role |
|------|------|
| `SKILL.md` | Spec-only pen path, type picker, cookbook, auth, `account.json` |
| `account.json` | Credentials (JSON). Download zip is filled; the repo copy is placeholders |
| `.env` | Same three keys, for hosts that load a skill-folder env file |
| `README.md` | Install notes |

## Manual / ClawHub

The ClawHub and git copies are **not ready to go**. `account.json` is placeholders (`13800138000` / `mgat_paste_token_…`). The agent must treat those as unconfigured.

If you did not download from 账户信息, put the three keys in `account.json` (or `skills.entries.mindgraph.env`). Never commit a real token. Regenerating the token in 账户信息 invalidates old skill folders and the Chrome extension.

```json
{
  "MINDGRAPH_BASE_URL": "https://test.mindspringedu.com",
  "MINDGRAPH_ACCOUNT": "138xxxxxxxx",
  "MINDGRAPH_TOKEN": "mgat_..."
}
```

**HTTP timeouts:** PNG render often needs **~180 seconds**.

## Publish updates (maintainers)

```bash
npm i -g clawhub
clawhub login
clawhub skill publish ./openclaw/skills/mindgraph --slug mindgraph --name "MindGraph" --version 1.8.0 --tags latest
```

Publish target: **1.8.0**. Keep `account.json` as placeholders in git.
