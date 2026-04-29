"""Normalize UTF-8 mojibake punctuation in Malay admin locale."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "src/locales/messages/ms/admin.ts"
    text = path.read_text(encoding="utf-8")

    # UTF-8 punctuation decoded byte-wise as latin-1 (three-byte sequences).
    bad_em = "".join(map(chr, (226, 128, 148)))  # em dash —
    bad_en = "".join(map(chr, (226, 128, 147)))  # en dash –
    ldquo = "".join(map(chr, (226, 128, 156)))  # “
    rdquo = "".join(map(chr, (226, 128, 157)))  # ”

    text = text.replace("\u00c2\u00b7", "\u00b7")  # Â· → ·
    bad_ge = "".join(map(chr, (226, 137, 165)))  # ≥
    bad_le = "".join(map(chr, (226, 137, 164)))  # ≤
    arrow = "".join(map(chr, (226, 134, 146)))  # → (UTF-8 E2 86 92 as mojibake)

    text = text.replace(bad_em, "\u2014")  # — em dash
    text = text.replace(bad_en, "\u2013")  # – en dash
    text = text.replace(bad_ge, "\u2265")  # ≥
    text = text.replace(bad_le, "\u2264")  # ≤
    text = text.replace(arrow, "\u2192")  # →
    text = text.replace(ldquo, "\u201c")  # “
    text = text.replace(rdquo, "\u201d")  # ”
    text = text.replace("Î£", "\u03a3")  # Î£ → Σ

    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
