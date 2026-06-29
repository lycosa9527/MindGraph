from collections.abc import Sequence
from typing import Any

windows: Sequence[Any]

def create_window(
    title: str,
    url: str,
    *,
    width: int = ...,
    height: int = ...,
    confirm_close: bool = ...,
) -> Any: ...
def start(*, gui: str = ...) -> None: ...
