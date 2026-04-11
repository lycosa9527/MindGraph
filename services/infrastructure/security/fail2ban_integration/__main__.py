"""python -m services.infrastructure.security.fail2ban_integration"""

from __future__ import annotations

import sys

from services.infrastructure.security.fail2ban_integration.cli import main

if __name__ == "__main__":
    sys.exit(main())
