"""Per-mascot complete scenes. Fifty each, plus pair clips in interactions."""

from __future__ import annotations

from scripts.desktop_pet.actions.black import ACTIONS as BLACK_ACTIONS
from scripts.desktop_pet.actions.pack import PetAction
from scripts.desktop_pet.actions.raven import ACTIONS as RAVEN_ACTIONS
from scripts.desktop_pet.actions.schnauzer import ACTIONS as SCHNAUZER_ACTIONS
from scripts.desktop_pet.actions.siamese import ACTIONS as SIAMESE_ACTIONS
from scripts.desktop_pet.actions.white import ACTIONS as WHITE_ACTIONS

ACTIONS_BY_SLUG: dict[str, tuple[PetAction, ...]] = {
    "black": BLACK_ACTIONS,
    "white": WHITE_ACTIONS,
    "siamese": SIAMESE_ACTIONS,
    "raven": RAVEN_ACTIONS,
    "schnauzer": SCHNAUZER_ACTIONS,
}


def actions_for(slug: str) -> tuple[PetAction, ...]:
    """Return the fifty scenes for one mascot."""
    found = ACTIONS_BY_SLUG.get(slug)
    if found is None:
        raise KeyError(slug)
    return found
