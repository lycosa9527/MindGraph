"""Resize/compress README assets for GitHub."""

from pathlib import Path

from PIL import Image

ASSETS = Path("docs/assets")
SPECS = {
    "readme-hero": 1600,
    "readme-diagrams": 1200,
    "readme-canvas": 1600,
}


def main() -> None:
    """Downscale PNG assets to progressive JPEGs and remove the PNGs."""
    for name, max_w in SPECS.items():
        src = ASSETS / f"{name}.png"
        if not src.exists():
            print(f"skip missing {src}")
            continue
        img = Image.open(src).convert("RGB")
        print(name, "src", img.size, src.stat().st_size)
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.Resampling.LANCZOS)
        jpg = ASSETS / f"{name}.jpg"
        img.save(jpg, "JPEG", quality=82, optimize=True, progressive=True)
        print(" ->", jpg, jpg.stat().st_size)
        src.unlink()
        print(" removed", src)


if __name__ == "__main__":
    main()
