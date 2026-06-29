# WeChat local read — reference matrix

MindGraph file-reader reads WeChat chat DBs on Windows. Implementation is a **blend** of these projects (logic only; no code copy):

| Capability | WeChat 3.x (`WeChat.exe`) | WeChat 4.0.x (`Weixin.exe`) | WeChat 4.1+ (`Weixin.exe`) |
|------------|---------------------------|-----------------------------|----------------------------|
| Data layout | `WeChat Files/wxid_*/Msg/` | `xwechat_files/*/db_storage/` | same as 4.0 |
| DB crypto | SQLCipher 3 — PBKDF2-SHA1, 64k iter | SQLCipher 4 — raw `enc_key` cached in memory | SQLCipher 4 — **passphrase** + PBKDF2-SHA512 256k |
| Key scan | [chatlog](https://github.com/svcvit/chatlog) `v3_windows.go` — `WeChatWin.dll` struct pattern | [wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) `find_all_keys_windows.py` — `x'<hex>'` memory scan | [chatlog](https://github.com/svcvit/chatlog) `v4_windows.go` — private RW region struct pattern |
| Fallback | — | passphrase scan (if mis-detected as 4.0) | **4.1.0–4.1.10.30:** chatlog passphrase scan → wx_key.dll; **≥ 4.1.10.31:** wx_key.dll hook only (passphrase no longer in heap) |
| Image `.dat` | XOR only (legacy) | V1/V2 + AES in memory | [wx_key](https://github.com/ycccccccy/wx_key) `image_key_service.dart` — template `*_t.dat` + memory scan |

## Three crypto cases in code

| `client_variant` | Detection | Key extraction order |
|------------------|-----------|----------------------|
| `v3` | `WeChat Files` layout, `WeChat.exe` | WeChatWin.dll scan → wx_key.dll |
| `v4` | `db_storage` + Weixin **&lt; 4.1** | `x'hex'` full memory scan ([wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt)) → passphrase → wx_key.dll |
| `v4.1` | `db_storage` + Weixin **≥ 4.1** (PE version) | **4.1.0–4.1.10.30:** passphrase scan → wx_key.dll hook; **≥ 4.1.10.31:** wx_key.dll hook only |

[wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) targets **4.0-style** raw key caching. It does not document 4.1 passphrase extraction; 4.1+ needs chatlog/wx_key logic above.

## Module map

| File | Role |
|------|------|
| `wechat_version.py` | Weixin.exe PE version → `v4` vs `v4.1` |
| `wechat_key_extract.py` | Three-case orchestrator |
| `wechat_crypto.py` | SQLCipher 4 constants + HMAC validation |
| `wechat_v3.py` | SQLCipher 3 decrypt + validation |
| `wechat_v41.py` | 4.1+ passphrase → per-DB enc_key |
| `wechat_scan_common.py` | Shared Windows memory scan helpers |
| `wechat_wcdb.py` | SQLCipher 4 page decrypt + decrypted DB cache |
| `wechat_wxkey_dll.py` | Optional ctypes wrapper for `wx_key.dll` |
| `wechat_image.py` | Image cache XOR/AES key extraction + `.dat` decode |
| `wechat_db_reader.py` | Sessions/messages from decrypted DBs |

## wx_key.dll (Weixin 4.1.10.31+ required; optional fallback on older 4.1)

Weixin **4.1.10.31+** no longer keeps the WCDB passphrase in plaintext heap memory. Passive RAM scan cannot work; the app uses [wx_key.dll](https://github.com/ycccccccy/wx_key) hook only (`InitializeHook` / `PollKeyData`).

On older 4.1 builds, wx_key.dll is the fallback when passphrase scan fails. It **injects hook shellcode** into `Weixin.exe` and may require **Administrator** — unlike the normal Python scan, which only uses `ReadProcessMemory` and usually runs as a normal user.

Place `wx_key.dll` from [wx_key Releases](https://github.com/ycccccccy/wx_key/releases) at:

- `clients/file-reader/tools/wx_key.dll`, or
- beside `mindgraph-file-reader.exe`

Do not put the DLL path in a folder with Chinese characters (upstream requirement).

## No admin?

| Mode | Admin needed? |
|------|----------------|
| Export folder → upload | **No** — always works |
| v3 / v4.0 live DB (memory scan) | **Usually no** — same-user `ReadProcessMemory` |
| v4.1 live DB (passphrase scan, 4.1.0–4.1.10.30) | **Usually no** — same as above |
| wx_key.dll hook (4.1.10.31+ or fallback) | **Often yes** — process injection |
| [wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) | Documents admin for Windows, but read-only scan is the same model as ours |

## Image keys

After DB keys work, image decryption needs a separate **image AES key** (16 bytes) and **XOR key** (1 byte). wx_key recommends: restart WeChat, open Moments images full-size 2–3 times, then capture keys immediately.
