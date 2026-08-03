"""Fetch recent mind maps from PostgreSQL for vector-export verification."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def main() -> int:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("NO_DATABASE_URL")
        return 2

    try:
        import psycopg
    except ImportError:
        try:
            import psycopg2 as psycopg  # type: ignore
        except ImportError:
            print("NO_PSYCOPG")
            return 3

    out_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pg_mindmaps"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = psycopg.connect(url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, diagram_type, language, spec
        FROM diagrams
        WHERE NOT is_deleted
          AND diagram_type IN ('mind_map', 'mindmap')
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 12
        """
    )
    rows = cur.fetchall()
    print(f"FOUND {len(rows)}")

    candidates: list[dict] = []
    for row in rows:
        diagram_id, title, dtype, lang, spec = row
        if isinstance(spec, str):
            spec = json.loads(spec)
        nodes = spec.get("nodes") or []
        texts = " ".join(str(node.get("text") or "") for node in nodes)
        has_cn = any("\u4e00" <= ch <= "\u9fff" for ch in texts)
        has_en = any("a" <= ch.lower() <= "z" for ch in texts)
        candidates.append(
            {
                "id": diagram_id,
                "title": title,
                "type": dtype,
                "lang": lang,
                "nodes": len(nodes),
                "has_cn": has_cn,
                "has_en": has_en,
                "spec": spec,
            }
        )
        print(
            json.dumps(
                {
                    "id": diagram_id,
                    "title": title,
                    "type": dtype,
                    "lang": lang,
                    "nodes": len(nodes),
                    "has_cn": has_cn,
                    "has_en": has_en,
                },
                ensure_ascii=False,
            )
        )

    picked: list[dict] = []
    for item in candidates:
        if item["has_cn"] and not any(p.get("tag") == "cn" for p in picked):
            picked.append({**item, "tag": "cn"})
        elif item["has_en"] and not any(p.get("tag") == "en" for p in picked):
            picked.append({**item, "tag": "en"})
        if len(picked) >= 3:
            break
    for item in candidates:
        if len(picked) >= 3:
            break
        if any(p["id"] == item["id"] for p in picked):
            continue
        picked.append({**item, "tag": "extra"})

    for index, item in enumerate(picked):
        path = out_dir / f"mindmap_{index + 1}_{item['tag']}.json"
        payload = {
            "id": item["id"],
            "title": item["title"],
            "diagram_type": item["type"],
            "spec": item["spec"],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE {path} title={item['title']}")

    cur.close()
    conn.close()
    return 0 if picked else 1


if __name__ == "__main__":
    sys.exit(main())
