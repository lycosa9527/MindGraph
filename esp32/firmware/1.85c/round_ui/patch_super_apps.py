#!/usr/bin/env python3
"""Keep Super init moving on this 1.85C PSRAM heap.

- Skip App Store at boot (Settings + Files need the RAM).
- Continue if a registered app fails to install.
- Always complete run_task_sync promises so a GUI-worker bad_alloc
  cannot leave the startup logo up forever.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
MANAGER_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_core"
    / "src"
    / "app"
    / "manager.cpp"
)
IMPL_HPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_core"
    / "src"
    / "private"
    / "system"
    / "impl.hpp"
)

FAIL_OLD = (
    '            BROOKESIA_LOGW("Registered app install failed: provider(%1%), '
    'error(%2%)", name, result.error());\n'
    "            return std::unexpected(result.error());\n"
)
FAIL_NEW = (
    '            BROOKESIA_LOGW("Registered app install failed: provider(%1%), '
    'error(%2%); continuing Super init", name, result.error());\n'
    "            continue;\n"
)

SKIP_MARKER = "Skipping registered app on 1.85C"
SKIP_OLD = """    for (auto &[name, provider] : providers) {
        if (!provider) {
            BROOKESIA_LOGW("App provider is null: name(%1%)", name);
            continue;
        }
"""
SKIP_NEW = """    for (auto &[name, provider] : providers) {
        if (!provider) {
            BROOKESIA_LOGW("App provider is null: name(%1%)", name);
            continue;
        }
        if (name == "brookesia.general.app_store") {
            BROOKESIA_LOGW("Skipping registered app on 1.85C: %1%", name);
            continue;
        }
"""

SYNC_OLD = """        auto result_promise = std::make_shared<boost::promise<Result>>();
        auto result_future = result_promise->get_future();
        auto task = [result_promise, fn = std::forward<Fn>(fn)]() mutable {
            result_promise->set_value(fn());
        };
        if (!task_scheduler_->post(std::move(task), nullptr, group)) {
            return std::move(post_error_result);
        }
        return result_future.get();
"""
SYNC_NEW = """        auto result_promise = std::make_shared<boost::promise<Result>>();
        auto result_future = result_promise->get_future();
        auto task = [result_promise, fn = std::forward<Fn>(fn)]() mutable {
            try {
                result_promise->set_value(fn());
            } catch (...) {
                result_promise->set_exception(std::current_exception());
            }
        };
        if (!task_scheduler_->post(std::move(task), nullptr, group)) {
            return std::move(post_error_result);
        }
        try {
            return result_future.get();
        } catch (...) {
            return std::move(post_error_result);
        }
"""


def replace_once(path: Path, old: str, new: str, already: str) -> int:
    """Replace old with new if needed. 0 ok, 1 missing."""
    text = path.read_text()
    if already in text:
        print(f"already patched {path.name}")
        return 0
    if old not in text:
        print(f"block not found in {path}")
        return 1
    path.write_text(text.replace(old, new, 1))
    print(f"patched {path}")
    return 0


def main() -> int:
    if not MANAGER_CPP.is_file() or not IMPL_HPP.is_file():
        print("missing Super core sources")
        return 1
    status = 0
    status |= replace_once(MANAGER_CPP, FAIL_OLD, FAIL_NEW, FAIL_NEW)
    status |= replace_once(MANAGER_CPP, SKIP_OLD, SKIP_NEW, SKIP_MARKER)
    status |= replace_once(IMPL_HPP, SYNC_OLD, SYNC_NEW, "set_exception(std::current_exception())")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
