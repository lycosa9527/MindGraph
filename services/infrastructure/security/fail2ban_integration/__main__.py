"""python -m services.infrastructure.security.fail2ban_integration

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import sys

from services.infrastructure.security.fail2ban_integration.cli import main

if __name__ == "__main__":
    sys.exit(main())
