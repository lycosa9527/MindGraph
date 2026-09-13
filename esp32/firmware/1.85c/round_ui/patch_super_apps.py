#!/usr/bin/env python3
"""Keep Super init moving on this 1.85C PSRAM heap.

- Skip App Store and Files at boot (Settings + Kitty need the RAM).
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
LIFECYCLE_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "system_lifecycle.cpp"
)
RESOURCES_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_core"
    / "src"
    / "system"
    / "resources.cpp"
)
NAV_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "system_navigation.cpp"
)
PACKAGE_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_core"
    / "src"
    / "app"
    / "package_scan.cpp"
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

SKIP_MARKER = "brookesia.general.files"
SKIP_OLD = """    for (auto &[name, provider] : providers) {
        if (!provider) {
            BROOKESIA_LOGW("App provider is null: name(%1%)", name);
            continue;
        }
"""
SKIP_STORE_ONLY = """        if (name == "brookesia.general.app_store") {
            BROOKESIA_LOGW("Skipping registered app on 1.85C: %1%", name);
            continue;
        }
"""
SKIP_NEW = """    for (auto &[name, provider] : providers) {
        if (!provider) {
            BROOKESIA_LOGW("App provider is null: name(%1%)", name);
            continue;
        }
        if (name == "brookesia.general.app_store" || name == "brookesia.general.files") {
            BROOKESIA_LOGW("Skipping registered app on 1.85C: %1%", name);
            continue;
        }
"""
SKIP_BOTH = """        if (name == "brookesia.general.app_store" || name == "brookesia.general.files") {
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

REFRESH_OLD = """    if (!shell_app_) {
        return {};
    }
    return shell_app_->refresh_launcher();
"""
REFRESH_NEW = """    if (!shell_app_) {
        return {};
    }
    auto refresh_result = shell_app_->refresh_launcher();
    if (!refresh_result) {
        BROOKESIA_LOGW(
            "Launcher refresh after app change failed: %1%; keeping installed apps",
            refresh_result.error()
        );
    }
    return {};
"""

ICON_PARSE_OLD = """    auto image = load_app_icon_image(record.info.manifest, resolve_app_resource_dir(record.info.manifest));
    if (!image) {
        return std::unexpected(image.error());
    }
"""
ICON_PARSE_NEW = """    auto image = load_app_icon_image(record.info.manifest, resolve_app_resource_dir(record.info.manifest));
    if (!image) {
        BROOKESIA_LOGW(
            "App icon skipped: app(%1%), error(%2%)",
            record.info.manifest.id,
            image.error()
        );
        return {};
    }
"""

ICON_REG_OLD = """    if (!result) {
        return std::unexpected("Failed to register app icon resource: " + result.error());
    }
"""
ICON_REG_NEW = """    if (!result) {
        BROOKESIA_LOGW(
            "App icon register skipped: app(%1%), error(%2%)",
            record.info.manifest.id,
            result.error()
        );
        return {};
    }
"""

RESTORE_OLD = """            auto page_result = shell_app_->show_page(pending_shell_page_);
            if (!page_result) {
                return page_result;
            }
            return shell_app_->set_foreground_app(std::nullopt);
"""
RESTORE_NEW = """            auto page_result = shell_app_->show_page(pending_shell_page_);
            if (!page_result) {
                return page_result;
            }
            auto refresh_result = shell_app_->refresh_launcher();
            if (!refresh_result) {
                BROOKESIA_LOGW("Launcher refresh on restore failed: %1%", refresh_result.error());
            }
            return shell_app_->set_foreground_app(std::nullopt);
"""

UNPACK_OLD = """            auto install_result = owner_.install_runtime_app(*manifest);
            if (!install_result) {
                return std::unexpected(install_result.error());
            }
"""
UNPACK_NEW = """            auto install_result = owner_.install_runtime_app(*manifest);
            if (!install_result) {
                BROOKESIA_LOGW(
                    "Skip runtime app install failure: path(%1%), error(%2%)",
                    package_dir.string(),
                    install_result.error()
                );
                continue;
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


def replace_all(path: Path, old: str, new: str, already: str) -> int:
    """Replace every copy of old. 0 ok, 1 missing."""
    text = path.read_text()
    if already in text:
        print(f"already patched {path.name}")
        return 0
    if old not in text:
        print(f"block not found in {path}")
        return 1
    path.write_text(text.replace(old, new))
    print(f"patched {path}")
    return 0


def main() -> int:
    """Patch Super app install to skip unused apps and survive GUI worker faults."""
    if not MANAGER_CPP.is_file() or not IMPL_HPP.is_file():
        print("missing Super core sources")
        return 1
    status = 0
    status |= replace_once(MANAGER_CPP, FAIL_OLD, FAIL_NEW, FAIL_NEW)
    if SKIP_BOTH in MANAGER_CPP.read_text():
        print(f"already patched {MANAGER_CPP.name} files skip")
    elif SKIP_STORE_ONLY in MANAGER_CPP.read_text():
        status |= replace_once(MANAGER_CPP, SKIP_STORE_ONLY, SKIP_BOTH, SKIP_BOTH)
    else:
        status |= replace_once(MANAGER_CPP, SKIP_OLD, SKIP_NEW, SKIP_MARKER)
    status |= replace_once(IMPL_HPP, SYNC_OLD, SYNC_NEW, "set_exception(std::current_exception())")
    if LIFECYCLE_CPP.is_file():
        status |= replace_all(
            LIFECYCLE_CPP,
            REFRESH_OLD,
            REFRESH_NEW,
            "keeping installed apps",
        )
    if RESOURCES_CPP.is_file():
        status |= replace_once(RESOURCES_CPP, ICON_PARSE_OLD, ICON_PARSE_NEW, "App icon skipped:")
        status |= replace_once(RESOURCES_CPP, ICON_REG_OLD, ICON_REG_NEW, "App icon register skipped:")
    if NAV_CPP.is_file():
        status |= replace_once(NAV_CPP, RESTORE_OLD, RESTORE_NEW, "Launcher refresh on restore failed")
    if PACKAGE_CPP.is_file():
        status |= replace_once(PACKAGE_CPP, UNPACK_OLD, UNPACK_NEW, "Skip runtime app install failure")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
