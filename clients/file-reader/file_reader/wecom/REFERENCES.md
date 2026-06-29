# WeCom (企业微信 / WXWork) local read — reference matrix

MindGraph file-reader adds **live WeCom DB read** on Windows (like WeChat / DingTalk).
Implementation is a **blend of these projects** (logic only; no code copy).

## Open-source projects (curated)

| Project | Lang | Scope | Best for |
|---------|------|-------|----------|
| [ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) | Python | WeChat 4.x + **WXWork 5.x** | **Primary port target** — `wxwork_crypto.py`, `find_wxwork_keys.py`, `decrypt_wxwork_db.py`, `export_wxwork_messages.py` |
| [wuruxu/wechat-decrypt](https://github.com/wuruxu/wechat-decrypt) | Python | WeChat 4.0 fork | Cross-check wxSQLite3 / memory scan if ylytdeng breaks on a client build |
| [911061873/PyWeWorkFinance](https://github.com/911061873/PyWeWorkFinance) | Python | Official session archive SDK | **Not in scope** — server-side compliance API, not local desktop DB |

### Write-ups

| Source | Covers |
|--------|--------|
| [ylytdeng/wechat-decrypt README — 企业微信](https://github.com/ylytdeng/wechat-decrypt) | wxSQLite3 AES-128-CBC, RAM key scan, `Documents\WXWork` paths |
| [朱皮特 — WeChat Decrypt 工具箱](https://zhupite.com/sec/wechat-decrypt.html) | WeCom vs personal WeChat crypto comparison |
| [CSDN — 企业微信数据库解密](https://blog.csdn.net/weixin_30650039/article/details/95157751) | End-to-end flow: `find_wxwork_keys` → `decrypt_wxwork_db` → export |

> **Not in scope:** [企业微信开发者 — 会话内容导出](https://developer.work.weixin.qq.com/document/path/101380) — cloud export API with ID translation; different product surface.

## On-disk layout (Windows, 5.x)

```text
%UserProfile%\Documents\WXWork\
  <corp_or_account_id>\
    Data\                          # some installs: WXWork\<id>\Data
      session\session.db
      message\message.db
      message\message_*.db
      user\user.db
      contact\contact.db
      media_*\media_*.db
      ...
  <corp_id>\<user_id>\Data\        # alternate layout (two-level)
```

Encrypted pages use **wxSQLite3 AES-128-CBC** (not SQLCipher 4, not DingTalk ECB).

## Crypto (wxSQLite3 AES-128)

| Step | Detail | Reference |
|------|--------|-----------|
| Raw key | 16 bytes from **WXWork.exe RAM** while logged in | `find_wxwork_keys.py` |
| Per-page key | `MD5(raw_key + page_no_le32 + b"sAlT")` | `wxwork_crypto.py` |
| IV | SQLite3MultipleCiphers `sqlite3mcGenerateInitialVector(page_no)` | `wxwork_crypto.py` |
| Page 1 | Bytes 16–23 stay plaintext; swap + decrypt tail; prepend `SQLite format 3\x00` | `wxwork_crypto.py` |
| Verify | Decrypted page 1 must look like valid SQLite btree page 1 | `verify_wxsqlite3_aes128_key` |

Legacy SQLCipher params are tried as fallback during memory scan only (`VERIFY_CONFIGS` in upstream).

## Key extraction pain points

| Topic | Detail |
|-------|--------|
| Process | **WXWork.exe must be running** and user logged in |
| Admin | Memory read usually needs elevated / admin rights (same class as WeChat key scan) |
| 32-bit | WXWork 5.0.x is **32-bit WOW64** — cipher struct offsets in upstream assume 4-byte pointers |
| Per-DB keys | Each `.db` may have a different 16-byte key; cache as `rel_path → hex_key` |
| Salt | First 16 bytes of page 1 used as scan fingerprint (like SQLCipher salt) |

## SQLite schema (after decrypt)

| Path / table | Role | Reference |
|--------------|------|-----------|
| `session/session.db` → `conversation_table` | Session list | `export_wxwork_messages.py` |
| `message/message*.db` → `message_table`, `message_small_table` | Chat rows | same |
| `user/user.db` → `user_table` | Display names | same |

Conversation ID prefixes: `R:` group, `S:` single, `M:` external WeChat, `O:` app, `Y:` system.

## MindGraph module map (implemented)

| File | Port from |
|------|-----------|
| `wecom/discovery.py` | `find_wxwork_keys.auto_detect_wxwork_db_dir`, `collect_db_files` |
| `wecom/crypto.py` | `wxwork_crypto.py` |
| `wecom/key_extract.py` | `find_wxwork_keys.py` (hex scan + cipher struct) |
| `wecom/key_store.py` | `wechat/key_store.py` pattern (DPAPI cache) |
| `wecom/local.py` | Process + data-dir detection |
| `wecom/db_cache.py` | `decrypt_wxwork_db.py` |
| `wecom/db_reader.py` | `export_wxwork_messages.py` (sessions + text) |
| `wecom/probe.py` | UI unlock + session load |
| `gui.py` / `platform_status.py` | Live DB mode (fourth platform radio) |

## Comparison to WeChat / DingTalk

| | WeChat | DingTalk | WeCom |
|---|---|---|---|
| Key source | RAM / hook / cache | Disk (`user_config` + logs) | **RAM scan** |
| Cipher | SQLCipher 4 / WCDB | AES-128-ECB pages | **wxSQLite3 AES-128-CBC** |
| Admin | Sometimes | Usually no | **Usually yes** |
| Primary OSS | chatlog, wechat-decrypt | dingwave-V3 | **ylytdeng/wechat-decrypt** |

## Recommended port order

1. **wxwork_crypto.py** — page decrypt + key verify (unit-testable)
2. **find_wxwork_keys.py** — path detect + memory scan
3. **decrypt_wxwork_db.py** — cache decrypted DBs under `%TEMP%/mindgraph-file-reader/wecom-cache`
4. **export_wxwork_messages.py** — `conversation_table` + `message_*` text decode
5. GUI + DPAPI key cache (reuse WeChat patterns)

## Licenses

ylytdeng/wechat-decrypt: check repo LICENSE before copying large chunks; MindGraph ports algorithms with fresh code.
