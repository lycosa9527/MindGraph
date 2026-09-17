"""Contract tests for leftover Super Kitty address prefixes in Fun-ASR text.

Wake is English MultiNet (`ni hao kitty`), not this list. Firmware still
strips a leftover prefix from the request transcript after MultiNet hits.
"""

from __future__ import annotations


def _is_address(text: str) -> bool:
    folded = "".join(ch.lower() for ch in text if ch not in " \t,.:;!?'\"")
    prefixes = (
        "你好kitty",
        "你好凯蒂",
        "你好小猫",
        "nihaokitty",
        "nihaokaidi",
        "nihaoxiaomao",
    )
    return any(prefix in folded for prefix in prefixes)


def test_address_aliases() -> None:
    """Known leftover prefixes still match after punctuation and case fold."""
    assert _is_address("你好 kitty")
    assert _is_address("你好Kitty")
    assert _is_address("ni hao kitty")
    assert _is_address("你好凯蒂，把中心改成项目计划")
    assert _is_address("你好小猫")


def test_ambient_is_not_address() -> None:
    """Ordinary edit phrases are not treated as an address prefix."""
    assert not _is_address("把中心改成项目计划")
    assert not _is_address("今天天气怎么样")
