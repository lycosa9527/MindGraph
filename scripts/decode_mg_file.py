"""Decode a MindGraph .mg interchange file to JSON (MG v1.1 AES-GCM).

See docs/MG_FILE_FORMAT.md for the wire format. Codec source of truth:
frontend/src/utils/mgInterchange.ts
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

from Crypto.Cipher import AES

KEY_LABEL = b"MindGraph.MG.interchange.v1"
HEADER_LEN = 4
IV_LEN = 12
TAG_LEN = 16
MIN_LEN = HEADER_LEN + IV_LEN + TAG_LEN


def decode_mg_v1_1(data: bytes) -> dict:
    """Decrypt MG v1.1 bytes and return the JSON diagram spec."""
    if len(data) < MIN_LEN:
        raise ValueError(f"file too short ({len(data)} bytes; need >= {MIN_LEN})")
    if data[:2] != b"MG" or data[2] != 1 or data[3] != 1:
        raise ValueError(f"unsupported header {data[:4]!r} (expected MG v1.1)")
    iv = data[HEADER_LEN : HEADER_LEN + IV_LEN]
    blob = data[HEADER_LEN + IV_LEN :]
    ciphertext, tag = blob[:-TAG_LEN], blob[-TAG_LEN:]
    key = sha256(KEY_LABEL).digest()
    plain = AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(ciphertext, tag)
    parsed = json.loads(plain.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("decrypted payload is not a JSON object")
    return parsed


def _summarize(obj: dict) -> None:
    print("keys=", sorted(obj.keys())[:40])
    print("type=", obj.get("type") or obj.get("diagramType") or obj.get("diagram_type") or "")
    title = obj.get("title") or obj.get("name") or ""
    if not title and isinstance(obj.get("nodes"), list):
        for node in obj["nodes"]:
            if isinstance(node, dict) and node.get("type") == "topic":
                title = str(node.get("text") or "")
                break
    print("title=", title)
    nodes = obj.get("nodes")
    connections = obj.get("connections")
    if isinstance(nodes, list):
        print("nodes=", len(nodes))
    if isinstance(connections, list):
        print("connections=", len(connections))


def main(argv: list[str] | None = None) -> int:
    """CLI entry: decode .mg to JSON file and print a short summary."""
    parser = argparse.ArgumentParser(description="Decode MindGraph .mg (v1.1) to JSON")
    parser.add_argument("mg_path", type=Path, help="path to .mg file")
    parser.add_argument(
        "out_path",
        nargs="?",
        type=Path,
        default=None,
        help="output JSON path (default: tmp/<stem>.json)",
    )
    args = parser.parse_args(argv)
    src: Path = args.mg_path
    if not src.is_file():
        print(f"not a file: {src}", file=sys.stderr)
        return 2
    out = args.out_path if args.out_path is not None else Path("tmp") / f"{src.stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    obj = decode_mg_v1_1(src.read_bytes())
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    _summarize(obj)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
