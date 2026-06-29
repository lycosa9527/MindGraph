"""Inspect Weixin 4.x key_info.db on disk."""

from pathlib import Path
import sqlite3

login_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\all_users\login\rulerwang")
key_file = login_dir / "key_info.db"
print("key_info.db exists:", key_file.is_file())
if key_file.is_file():
    print("size:", key_file.stat().st_size)
    head = key_file.read_bytes()[:64]
    print("header hex:", head.hex())
    print("header ascii:", head[:16])
    try:
        conn = sqlite3.connect(key_file)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        print("tables:", [t[0] for t in tables])
        conn.close()
    except (OSError, sqlite3.Error) as exc:
        print("sqlite open failed:", exc)

for path in sorted(login_dir.glob("*")):
    print(" ", path.name, path.stat().st_size if path.is_file() else "dir")
