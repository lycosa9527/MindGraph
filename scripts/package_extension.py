"""Build a Microsoft Edge / Chrome Web Store zip with manifest.json at archive root."""

from __future__ import annotations

import argparse
from pathlib import Path

from utils.extension_store_packaging import DEFAULT_OUTPUT, build_store_zip


def main() -> None:
    """CLI entry: write store-ready extension zip."""
    parser = argparse.ArgumentParser(description="Package MindGraph extension for store upload.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output zip path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    out = build_store_zip(args.output)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
