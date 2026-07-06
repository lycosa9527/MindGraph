"""UTF-8 byte limit helpers for WeCom message bodies."""


def truncate_utf8(text: str, max_bytes: int) -> str:
    """Trim text so encoded UTF-8 length does not exceed max_bytes."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    limit = max_bytes
    while limit > 0:
        try:
            return encoded[:limit].decode("utf-8")
        except UnicodeDecodeError:
            limit -= 1
    return ""
