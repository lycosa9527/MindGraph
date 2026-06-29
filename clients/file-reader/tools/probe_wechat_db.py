"""One-off probe for local WeChat DB layout (dev only)."""

import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
for rel in ["session/session.db", "message/message_0.db", "contact/contact.db"]:
    p = ROOT / rel
    print("===", rel, "===")
    if not p.is_file():
        print("missing")
        continue
    try:
        conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 20")
        print("tables:", [r[0] for r in cur.fetchall()])
        conn.close()
        print("readable")
    except (OSError, sqlite3.Error) as exc:
        print("error:", exc)
