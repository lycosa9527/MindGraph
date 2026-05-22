"""
Feature Routers

Feature-specific endpoints for various application features.
"""

from .askonce import router as askonce_router
from .debateverse import router as debateverse_router
from .gewe import router as gewe_router
from .kitty import router as kitty_router
from .library import router as library_router
from .school_zone import router as school_zone_router

__all__ = [
    "askonce_router",
    "debateverse_router",
    "gewe_router",
    "kitty_router",
    "library_router",
    "school_zone_router",
]

# Backward compatibility aliases
askonce = askonce_router
debateverse = debateverse_router
gewe = gewe_router
kitty = kitty_router
library = library_router
school_zone = school_zone_router
