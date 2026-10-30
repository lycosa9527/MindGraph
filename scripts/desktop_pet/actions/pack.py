"""Build numbered pet actions from short rows."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class PetAction(TypedDict):
    """One complete scene. Costume replaces the everyday outfit."""

    id: str
    slug: str
    name: str
    prompt: str
    costume: NotRequired[str]


def pack(rows: tuple[tuple[str, str, str, str], ...]) -> tuple[PetAction, ...]:
    """Number rows from 01. The fourth field is a costume, or empty for everyday clothes."""
    actions: list[PetAction] = []
    for index, (slug, name, prompt, costume) in enumerate(rows, start=1):
        action: PetAction = {
            "id": f"{index:02d}",
            "slug": slug,
            "name": name,
            "prompt": prompt,
        }
        if costume:
            action["costume"] = costume
        actions.append(action)
    return tuple(actions)


def clip_id(action: PetAction) -> str:
    """Filename stem such as ``01-arcade``."""
    return f"{action['id']}-{action['slug']}"
