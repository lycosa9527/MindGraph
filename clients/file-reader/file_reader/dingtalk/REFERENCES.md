# DingTalk local read — reference matrix

MindGraph file-reader will add **live DingTalk DB read** on Windows (like WeChat).
Implementation should be a **blend of these projects** (logic only; no code copy).

## Open-source projects (curated)

| Project | Lang | V2 | V3 | Best for |
|---------|------|----|----|----------|
| [E2ern1ty/dingwave-V3](https://github.com/E2ern1ty/dingwave-V3) | Python | yes | yes | **Primary port target** — pure-Python decrypt, `tbconversation` / `tbmsg_*` parser, JSON export, auto-detect paths |
| [chiehw/dingwave](https://github.com/chiehw/dingwave) | Go | yes | yes | **V3 CLI + path docs** — `-k real_uid`, `-userconfig`, `gaea.log` UID discovery; fork of p1g3 with 2026-04 V3 support |
| [p1g3/dingwave](https://github.com/p1g3/dingwave) | Go | yes | no | **Original** — V2 decrypt, Web UI, 20+ message types, global search, `--token` for remote images |
| [V1rtu0l/dingwave](https://github.com/V1rtu0l/dingwave) | Go | yes | no | Early fork of p1g3; same V2 scope — use only if diffing p1g3/chiehw |
| [CrackerCat/dingwave](https://github.com/CrackerCat/dingwave) | Go | yes | no | Another p1g3 fork; no V3 additions |

### Reverse-engineering write-ups (crypto spec)

| Source | Covers |
|--------|--------|
| [Kanxue — 钉钉 V3 数据库 key 逆向 (thread-287455)](https://bbs.kanxue.com/thread-287455.htm) | **Authoritative V3 key**: `uid+salt` → PBKDF2-HMAC-SHA1(`666DingTalk888`, 8, **1000**, 32) → MD5 → AES-128 key; `salt` from Base64 `user_config` JSON |
| [Kanxue / unsafe.sh — 钉钉 PC 版数据库解密 (thread-255356)](https://bbs.pediy.com/thread-255356.htm) | **V2**: AES-128-ECB per 4096-byte page; key = `MD5(uid).hex()[:16]`; **`globalStorage/storage.db`** key from `cpuid(0)` formatted as `%d%d%d%d` |
| [chiehw/dingwave README — V3 section](https://github.com/chiehw/dingwave) | Windows paths, `real_uid` from `%AppData%\Roaming\DingTalk\log\gaea.log.*`, `user_config` location |

> **Not in scope:** CSDN “chat.db + session_key in memory” articles describe a **different** storage layout (newer/alternate builds). Current desktop `_v3` accounts use **`Roaming\DingTalk\{id}_v3\DBFiles\dingtalk.db`** — match dingwave family, not `%LOCALAPPDATA%\...\chat.db`.

## On-disk layout (Windows, V3)

```text
%AppData%\Roaming\DingTalk\
  globalStorage\storage.db          # meta DB; key = f(cpuid); maps accounts → *_v3 dirs
  log\gaea.log.*                    # search real_uid=123456789
  {hex_id}_v3\
    user_config                     # Base64 JSON → salt (32-char hex)
    DBFiles\dingtalk.db             # AES-128-ECB encrypted SQLite (4096-byte pages)
    DBFiles\dingtalk.db-wal         # copy with main db when DingTalk is open
    DBFiles\dingtalk.db-shm
    ImageFiles\  AudioFiles\  ...   # local attachments (optional phase 2)
```

## Crypto cases in code (planned)

| `client_variant` | Detection | Key derivation |
|------------------|-----------|----------------|
| `v2` | `{uid}_v2` folder | `AES_key = MD5(folder_uid).hexdigest()[:16]` (ASCII bytes) |
| `v3` | `{hex}_v3` folder | `password = real_uid + salt`; PBKDF2-SHA1(password, `666DingT`, 1000, 32) → MD5 → key[:16] |

Page decrypt (both): read file in 4096-byte blocks; full pages AES-128-ECB decrypt; verify `SQLite format 3\x00` header.

## UID discovery (V3 pain point)

| Method | Reference | Notes |
|--------|-----------|-------|
| `gaea.log.*` grep `real_uid=` | chiehw/dingwave README | Simplest on Windows; may miss if logs rotated |
| Decrypt `globalStorage/storage.db` → query uid | Kanxue 287455, E2ern1ty config.py | Needs `cpuid(0)` → `%d%d%d%d` key (same as V2 meta DB) |
| macOS plist `safemode_last_crash_uid` | E2ern1ty/dingwave-V3 | Not applicable to file-reader Windows build |
| Manual / cached | E2ern1ty env `DINGTALK_UID` | Fallback UI if auto-detect fails |

**Important:** V3 folder name (`180ae37e719cf00d6137_v3`) is **not** the `-k` / key uid.

## SQLite schema (after decrypt)

| Table | Role | Reference file |
|-------|------|----------------|
| `tbconversation` | Session list (`cid`, `type`, `title`, `lastModify`, …) | E2ern1ty `parser.py` → `get_conversations` |
| `tbmsg_000` … `tbmsg_127` | Sharded messages per `cid` | E2ern1ty `parser.py` → `_find_msg_table` |
| `tbuser_profile_v2` | Display names for 1:1 chats | E2ern1ty `parser.py` → `get_user_profile` |

Message `contentType` → text extraction: start with types **1 (text)**, **1200 (rich text)**, **3100 (quote)**; skip media-only types for RAG (same scope as WeChat export).

## MindGraph module map (implemented)

| File | Port from |
|------|-----------|
| `dingtalk/local.py` | E2ern1ty `config.py` + chiehw path docs |
| `dingtalk/discovery.py` | Account scan, V3 salt, `gaea.log` UID |
| `dingtalk/crypto.py` | E2ern1ty `decrypt.py` + Kanxue 287455 |
| `dingtalk/db_cache.py` | Copy + decrypt cache under `%APPDATA%/MindGraph/dingtalk-cache` |
| `dingtalk/db_reader.py` | E2ern1ty `parser.py` (sessions + messages) |
| `dingtalk/probe.py` | UI unlock + session load |
| `dingtalk/folder_export.py` | Manual `.txt` export (legacy path) |
| `chat/messages.py`, `chat/paths.py`, `chat/conversation_list.py` | Shared WeChat + DingTalk export/upload |
| `gui.py` / `platform_status.py` | Live DB mode + checkbox list for both platforms |

## Operational notes

| Topic | Detail |
|-------|--------|
| DB lock | Copy `dingtalk.db` (+ `-wal`/`-shm`) to temp with retries while DingTalk runs — E2ern1ty `decrypt.py` `copy_encrypted_db` |
| Admin | **Not required** (unlike WeChat wx_key hook) — filesystem + derived key only |
| Remote images | p1g3/chiehw `--token` (DingTalk web cookie) — **optional**; not needed for text export/upload |
| Licenses | E2ern1ty/dingwave-V3: **MIT**; verify p1g3/chiehw before copying large chunks |

## Recommended port order

1. **E2ern1ty/dingwave-V3** — `decrypt.py` + `config.py` (V2/V3 detect, salt, copy-with-retry)
2. **E2ern1ty/dingwave-V3** — `parser.py` (conversations + text messages)
3. **chiehw/dingwave** — cross-check V3 CLI + `real_uid` log grep
4. **Kanxue 287455** — verify PBKDF2 constants if a client update breaks decrypt
5. **p1g3/dingwave** — extra message types / edge cases (read-only reference)

## Comparison to WeChat file-reader

| | WeChat | DingTalk |
|---|---|--------|
| Key source | RAM scan / wx_key.dll | `user_config` + `real_uid` on disk |
| Cipher | SQLCipher 4 | AES-128-ECB pages |
| Admin | Sometimes | Usually no |
| Primary OSS | chatlog, wechat-decrypt, wx_key | **dingwave-V3**, chiehw/dingwave |
