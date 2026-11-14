"""Launch art is the first console output. Later startup records follow it."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from services.infrastructure.lifecycle.startup_banner import mindgraph_startup_banner_lines

_REPO = Path(__file__).resolve().parents[1]


def test_banner_lines_include_art_and_version() -> None:
    """The block-letter mark and the VERSION file both ship in the launch art."""
    lines = mindgraph_startup_banner_lines()
    version = (_REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert any("███╗" in line for line in lines)
    assert any("╚═╝" in line for line in lines)
    assert any(version in line for line in lines)


def test_live_setup_logging_keeps_art_ahead_of_records() -> None:
    """Real logging setup holds console records until release, and the log file gets them."""
    script = textwrap.dedent(
        """
        import logging
        import sys
        import traceback
        from pathlib import Path

        class Capture:
            def __init__(self) -> None:
                self.chunks: list[str] = []
                self.encoding = "utf-8"

            def write(self, data: str) -> int:
                self.chunks.append(data)
                return len(data)

            def flush(self) -> None:
                return None

            def isatty(self) -> bool:
                return False

        capture = Capture()
        sys.stdout = capture
        sys.stderr = capture
        try:
            from services.infrastructure.lifecycle.startup_banner import (
                print_launch_banner_and_hold_logs,
                release_held_startup_logs,
            )

            print_launch_banner_and_hold_logs()
            logging.getLogger("probe").error("held-early")

            from services.infrastructure.utils.logging_config import setup_logging

            setup_logging()
            logging.getLogger("probe").error("held-after-setup")
            before = "".join(capture.chunks)
            if "held-early" in before or "held-after-setup" in before:
                raise SystemExit("console showed logs before release")
            log_text = "\\n".join(path.read_text(encoding="utf-8") for path in Path("logs").glob("*.log"))
            if "held-early" not in log_text or "held-after-setup" not in log_text:
                raise SystemExit("log file missed startup records")
            release_held_startup_logs()
            after = "".join(capture.chunks)
            art_at = after.index("███╗")
            early_at = after.index("held-early")
            later_at = after.index("held-after-setup")
            if not art_at < early_at < later_at:
                raise SystemExit("console order was not art, then early log, then later log")
            if after.count("held-early") != 1 or after.count("held-after-setup") != 1:
                raise SystemExit("startup line was logged more than once")
            if log_text.count("held-early") != 1 or log_text.count("held-after-setup") != 1:
                raise SystemExit("startup line was written to the log file more than once")
        except SystemExit:
            sys.__stderr__.write("".join(capture.chunks))
            raise
        except Exception:
            sys.__stderr__.write(traceback.format_exc())
            sys.__stderr__.write("".join(capture.chunks))
            raise
        print("GATE_OK", file=sys.__stdout__)
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO)
    with tempfile.TemporaryDirectory() as temp_dir:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=temp_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "GATE_OK" in completed.stdout
