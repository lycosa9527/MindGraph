"""
Feature Routers

Feature-specific endpoints for various application features.
"""

from .askonce import router as askonce_router
from .debateverse import router as debateverse_router
from .gewe import router as gewe_router
from .library import router as library_router
from .school_zone import router as school_zone_router
from .tab_mode import router as tab_mode_router
from .voice import router as voice_router

__all__ = [
    "askonce_router",
    "debateverse_router",
    "gewe_router",
    "library_router",
    "school_zone_router",
    "tab_mode_router",
    "voice_router",
]

# Backward compatibility aliases
askonce = askonce_router
debateverse = debateverse_router
gewe = gewe_router
library = library_router
school_zone = school_zone_router
tab_mode = tab_mode_router
voice = voice_router
