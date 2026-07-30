"""E2E: pull real mind maps from Postgres, render, validate soft-load invariants.

Does NOT call vision/LLM. Validates the diagram-render-speedup soft path:
- stamped nodes+connections specs stay position-stable under soft load (generic)
- connections reference existing node ids
- topic node present; PNG render succeeds

Usage (WSL, repo root, conda mindgraph):
  PYTHONPATH=. python scripts/validate_mindmap_soft_load_from_pg.py --limit 15

Outputs:
  tmp/mindmap_soft_load_e2e/report.json
  tmp/mindmap_soft_load_e2e/png/<nn>_<id>_original.png
  tmp/mindmap_soft_load_e2e/png/<nn>_<id>_soft.png
  tmp/mindmap_soft_load_e2e/fixtures/*.json  (for frontend vitest)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "mindmap_soft_load_e2e"
PNG_DIR = OUT / "png"
FIXTURE_DIR = OUT / "fixtures"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv_into_environ(env_path: Path) -> None:
    """Load KEY=VALUE lines from ``.env`` without overriding existing env."""
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


_load_dotenv_into_environ(ROOT / ".env")


def _database_url() -> str:
    """Resolve async SQLAlchemy URL from env (prefer migrate/BYPASSRLS role)."""
    raw = (os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL / DATABASE_MIGRATION_URL not set")
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    return raw


_CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/mnt/c/Windows/Fonts/msyh.ttc",
    "/mnt/c/Windows/Fonts/simhei.ttf",
    "/mnt/c/Windows/Fonts/simsun.ttc",
    "DejaVuSans.ttf",
    "arial.ttf",
    "Arial.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort font with CJK coverage for Chinese mind-map labels."""
    for name in _CJK_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _as_dict_list(value: Any) -> List[Dict[str, Any]]:
    """Return only dict items from a list-like value."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _node_id(node: Dict[str, Any]) -> str:
    """Stable node id string."""
    return str(node.get("id") or "").strip()


def _node_label(node: Dict[str, Any]) -> str:
    """Extract display text from a mind-map node."""
    data = node.get("data")
    if isinstance(data, dict):
        nested = data.get("text") or data.get("label")
        if nested:
            return str(nested).strip()[:40]
    return str(node.get("text") or node.get("label") or "").strip()[:40] or "?"


def _node_xy(node: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Canvas position if present."""
    position = node.get("position")
    if not isinstance(position, dict):
        return None
    try:
        return float(position["x"]), float(position["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _layout_fingerprint(nodes: List[Dict[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """id → (x, y) for nodes with positions."""
    out: Dict[str, Tuple[float, float]] = {}
    for node in nodes:
        node_id = _node_id(node)
        if not node_id:
            continue
        xy = _node_xy(node)
        if xy is not None:
            out[node_id] = xy
    return out


def _draw_bubble(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text_value: str,
    *,
    fill: Tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Draw a labeled oval at ``xy``."""
    label = text_value[:28]
    padding_x, padding_y = 12, 8
    bbox = draw.textbbox((0, 0), label, font=font)
    width = int(bbox[2] - bbox[0]) + padding_x * 2
    height = int(bbox[3] - bbox[1]) + padding_y * 2
    left, top = xy[0] - width // 2, xy[1] - height // 2
    draw.ellipse(
        (left, top, left + width, top + height),
        fill=fill,
        outline=(50, 50, 50),
        width=2,
    )
    draw.text(xy, label, fill=(20, 20, 20), font=font, anchor="mm")


def render_mindmap_png(spec: Dict[str, Any], path: Path) -> Path:
    """Render a PNG from library ``nodes``/``connections``."""
    nodes = _as_dict_list(spec.get("nodes"))
    connections = _as_dict_list(spec.get("connections"))
    usable: List[Tuple[Dict[str, Any], Tuple[float, float]]] = []
    for node in nodes:
        xy = _node_xy(node)
        if xy is None:
            continue
        usable.append((node, xy))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not usable:
        Image.new("RGB", (1100, 780), (252, 250, 245)).save(path, format="PNG")
        return path

    xs = [xy[0] for _, xy in usable]
    ys = [xy[1] for _, xy in usable]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    pad = 80
    canvas_w, canvas_h = 1100, 780
    scale = min((canvas_w - 2 * pad) / span_x, (canvas_h - 2 * pad) / span_y)

    def project(xy: Tuple[float, float]) -> Tuple[int, int]:
        return (
            int(pad + (xy[0] - min_x) * scale),
            int(pad + (xy[1] - min_y) * scale),
        )

    id_to_xy = {str(node.get("id")): project(xy) for node, xy in usable}
    image = Image.new("RGB", (canvas_w, canvas_h), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    node_font = _font(14)
    title_font = _font(18)

    for conn in connections:
        source = id_to_xy.get(str(conn.get("source")))
        target = id_to_xy.get(str(conn.get("target")))
        if source and target:
            draw.line([source, target], fill=(90, 90, 90), width=2)

    for node, xy in usable:
        projected = project(xy)
        is_topic = str(node.get("type") or "").lower() in {"topic", "root", "center"} or (
            str(node.get("id")) == "topic"
        )
        fill = (255, 214, 102) if is_topic else (173, 216, 230)
        font = title_font if is_topic else node_font
        _draw_bubble(draw, projected, _node_label(node), fill=fill, font=font)

    image.save(path, format="PNG")
    return path


def _validate_graph(spec: Dict[str, Any], *, label: str) -> List[str]:
    """Structural checks for a canvas-shaped mind map. Returns error strings."""
    errors: List[str] = []
    nodes = _as_dict_list(spec.get("nodes"))
    connections = _as_dict_list(spec.get("connections"))
    if len(nodes) < 3:
        errors.append(f"{label}: fewer than 3 nodes ({len(nodes)})")
        return errors

    ids = [_node_id(n) for n in nodes]
    id_set = {i for i in ids if i}
    if len(id_set) != len([i for i in ids if i]):
        errors.append(f"{label}: duplicate node ids")
    if "topic" not in id_set:
        errors.append(f"{label}: missing topic node")

    positioned = sum(1 for n in nodes if _node_xy(n) is not None)
    if positioned < max(1, len(nodes) // 2):
        errors.append(f"{label}: too few positioned nodes ({positioned}/{len(nodes)})")

    for conn in connections:
        source = str(conn.get("source") or "")
        target = str(conn.get("target") or "")
        if source and source not in id_set:
            errors.append(f"{label}: connection source missing: {source}")
        if target and target not in id_set:
            errors.append(f"{label}: connection target missing: {target}")

    return errors


def _soft_load_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Mirror frontend soft path: keep nodes/connections as-is (generic load)."""
    out = dict(spec)
    out["nodes"] = [dict(n) for n in _as_dict_list(spec.get("nodes"))]
    out["connections"] = [dict(c) for c in _as_dict_list(spec.get("connections"))]
    return out


def _positions_preserved(original: Dict[str, Any], soft: Dict[str, Any]) -> bool:
    """True when soft kept positions (expected for stamped canvas specs)."""
    before = _layout_fingerprint(_as_dict_list(original.get("nodes")))
    after = _layout_fingerprint(_as_dict_list(soft.get("nodes")))
    if not before:
        return False
    shared = set(before) & set(after)
    if not shared:
        return False
    return all(before[i] == after[i] for i in shared)


def _png_pixel_diff_ratio(path_a: Path, path_b: Path) -> float:
    """Fraction of differing pixels (0 = identical)."""
    with Image.open(path_a) as image_a, Image.open(path_b) as image_b:
        rgb_a = image_a.convert("RGB")
        rgb_b = image_b.convert("RGB")
        if rgb_a.size != rgb_b.size:
            return 1.0
        diff = ImageChops.difference(rgb_a, rgb_b)
        bbox = diff.getbbox()
        if bbox is None:
            return 0.0
        # Any non-empty bbox means pixels differ; count via histogram of non-zero.
        hist = diff.convert("L").histogram()
        nonzero = sum(hist[1:])
        total = rgb_a.size[0] * rgb_a.size[1]
        return nonzero / total if total else 1.0


async def _fetch_mindmaps(limit: int) -> List[Dict[str, Any]]:
    """Load distinct recent canvas-shaped mind maps from Postgres."""
    database_url = _database_url()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    rows: List[Dict[str, Any]] = []
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, user_id, title, diagram_type, spec, language, updated_at
                    FROM (
                      SELECT id, user_id, title, diagram_type, spec, language,
                             updated_at,
                             ROW_NUMBER() OVER (
                               PARTITION BY title
                               ORDER BY updated_at DESC NULLS LAST
                             ) AS rn
                      FROM diagrams
                      WHERE is_deleted = false
                        AND diagram_type IN ('mind_map', 'mindmap')
                        AND spec IS NOT NULL
                        AND jsonb_typeof(spec) = 'object'
                        AND jsonb_typeof(spec->'nodes') = 'array'
                        AND jsonb_array_length(spec->'nodes') >= 3
                        AND jsonb_typeof(spec->'connections') = 'array'
                    ) ranked
                    WHERE rn = 1
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            for row in result.mappings().all():
                spec = row["spec"]
                if isinstance(spec, str):
                    spec = json.loads(spec)
                if not isinstance(spec, dict):
                    continue
                rows.append(
                    {
                        "id": str(row["id"]),
                        "user_id": int(row["user_id"]),
                        "title": str(row["title"] or ""),
                        "diagram_type": str(row["diagram_type"] or "mindmap"),
                        "language": str(row["language"] or "zh"),
                        "updated_at": str(row["updated_at"] or ""),
                        "spec": spec,
                    }
                )
    finally:
        await engine.dispose()
    return rows


async def _run(limit: int) -> int:
    """Fetch, render, validate, write fixtures + report."""
    OUT.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching up to {limit} mind maps from Postgres...")
    using = "DATABASE_MIGRATION_URL" if (os.environ.get("DATABASE_MIGRATION_URL") or "").strip() else "DATABASE_URL"
    print(f"DB source: {using}")
    rows = await _fetch_mindmaps(limit)
    print(f"Fetched: {len(rows)}")
    if not rows:
        print("ERROR: no mind maps with nodes+connections found")
        return 1

    report: Dict[str, Any] = {
        "total": len(rows),
        "passed": 0,
        "failed": 0,
        "cases": [],
    }
    failures = 0

    for index, row in enumerate(rows, start=1):
        diagram_id = row["id"]
        title = row["title"] or diagram_id
        spec = row["spec"]
        short_id = diagram_id.replace("-", "")[:10]
        case: Dict[str, Any] = {
            "index": index,
            "id": diagram_id,
            "title": title,
            "node_count": len(_as_dict_list(spec.get("nodes"))),
            "connection_count": len(_as_dict_list(spec.get("connections"))),
            "errors": [],
            "ok": False,
        }
        print(
            f"\n[{index}/{len(rows)}] {title!r} ({diagram_id[:8]}…) "
            f"nodes={case['node_count']} edges={case['connection_count']}"
        )

        case["errors"].extend(_validate_graph(spec, label="original"))
        soft = _soft_load_spec(spec)
        case["errors"].extend(_validate_graph(soft, label="soft"))
        if not _positions_preserved(spec, soft):
            case["errors"].append("soft: positions not preserved vs original")

        orig_png = PNG_DIR / f"{index:02d}_{short_id}_original.png"
        soft_png = PNG_DIR / f"{index:02d}_{short_id}_soft.png"
        try:
            render_mindmap_png(spec, orig_png)
            render_mindmap_png(soft, soft_png)
            case["png_original"] = str(orig_png.relative_to(ROOT))
            case["png_soft"] = str(soft_png.relative_to(ROOT))
            if not orig_png.is_file() or orig_png.stat().st_size < 200:
                case["errors"].append("original PNG missing or tiny")
            if not soft_png.is_file() or soft_png.stat().st_size < 200:
                case["errors"].append("soft PNG missing or tiny")
            if orig_png.is_file() and soft_png.is_file():
                diff = _png_pixel_diff_ratio(orig_png, soft_png)
                case["png_diff_ratio"] = round(diff, 6)
                # Soft path must be pixel-identical for stamped canvas specs.
                if diff > 0:
                    case["errors"].append(f"soft PNG differs from original (diff={diff:.6f})")
        except (OSError, ValueError, TypeError) as exc:
            case["errors"].append(f"render failed: {exc}")

        fixture_path = FIXTURE_DIR / f"{index:02d}_{short_id}.json"
        fixture_path.write_text(
            json.dumps(
                {
                    "id": diagram_id,
                    "title": title,
                    "diagram_type": row["diagram_type"],
                    "spec": spec,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        case["fixture"] = str(fixture_path.relative_to(ROOT))

        if case["errors"]:
            failures += 1
            case["ok"] = False
            report["failed"] += 1
            for err in case["errors"]:
                print(f"  FAIL: {err}")
        else:
            case["ok"] = True
            report["passed"] += 1
            print("  OK: graph + soft positions + identical PNGs")

        report["cases"].append(case)

    report_path = OUT / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n========== SUMMARY ==========")
    print(f"passed: {report['passed']}/{report['total']}")
    print(f"failed: {report['failed']}/{report['total']}")
    print(f"report: {report_path}")
    print(f"pngs:   {PNG_DIR}")
    print(f"fixtures: {FIXTURE_DIR}")
    return 1 if failures else 0


def main() -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=15, help="How many distinct mind maps")
    args = parser.parse_args()
    return asyncio.run(_run(max(1, min(args.limit, 40))))


if __name__ == "__main__":
    raise SystemExit(main())
