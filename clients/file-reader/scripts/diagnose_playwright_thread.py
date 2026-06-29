"""Run diagnose_playwright_launch.main() on a worker thread."""

from __future__ import annotations

import threading

from diagnose_playwright_launch import main


def test_launch_on_worker_thread() -> None:
    thread = threading.Thread(target=main, name="pw-worker", daemon=True)
    thread.start()
    thread.join(timeout=90)
    print("thread alive", thread.is_alive())


if __name__ == "__main__":
    test_launch_on_worker_thread()
