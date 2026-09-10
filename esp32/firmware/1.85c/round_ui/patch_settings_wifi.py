#!/usr/bin/env python3
"""Patch Settings Wi-Fi list, default-on switch, and saved AP seed.

Settings skips create_view when free PSRAM is under 320KB. After the
Settings DOM loads, that guard often creates zero rows, so scan looks empty.
A missing WifiEnabled NVS key also defaults the switch off and stops the
radio. SetConnectAp only stores the station target, so a boot-seeded AP
never appears under Saved networks until a connect succeeds.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_app_settings"
    / "src"
    / "settings_app.cpp"
)
WIFI_IPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_app_settings"
    / "src"
    / "service"
    / "wifi.ipp"
)
SERVICES_IPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_app_settings"
    / "src"
    / "service"
    / "services.ipp"
)
WIFI_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_service_wifi"
    / "src"
    / "service_wifi.cpp"
)

RESERVE_OLD = "static constexpr size_t WIFI_SLOT_MIN_FREE_PSRAM_BYTES = 320 * 1024;"
RESERVE_NEW = "static constexpr size_t WIFI_SLOT_MIN_FREE_PSRAM_BYTES = 80 * 1024;"

GUARD_OLD = """        if (i >= retained_slot_count) {
            const auto heap = ::esp_brookesia::lib_utils::MemoryProfiler::take_raw_heap_snapshot();
            if (heap.external_free != 0 && heap.external_free < WIFI_SLOT_MIN_FREE_PSRAM_BYTES) {
"""
GUARD_NEW = """        if (i >= retained_slot_count && i >= 2) {
            const auto heap = ::esp_brookesia::lib_utils::MemoryProfiler::take_raw_heap_snapshot();
            if (heap.external_free != 0 && heap.external_free < WIFI_SLOT_MIN_FREE_PSRAM_BYTES) {
"""

PREF_MISSING_OLD = """            "Settings Wi-Fi switch preference is not stored yet; default to off: %1%",
            result.error()
        );
        return false;
"""
PREF_MISSING_NEW = """            "Settings Wi-Fi switch preference is not stored yet; default to on: %1%",
            result.error()
        );
        return true;
"""

PREF_UNAVAIL_OLD = """        BROOKESIA_LOGW("Storage service is unavailable; default Settings Wi-Fi switch to off");
        return false;
"""
PREF_UNAVAIL_NEW = """        BROOKESIA_LOGW("Storage service is unavailable; default Settings Wi-Fi switch to on");
        return true;
"""

PREF_KEY_OLD = (
    '        BROOKESIA_LOGW("Failed to resolve Settings Wi-Fi switch preference key: %1%",'
    " kv_name.error());\n"
    "        return false;\n"
)
PREF_KEY_NEW = (
    '        BROOKESIA_LOGW("Failed to resolve Settings Wi-Fi switch preference key: %1%",'
    " kv_name.error());\n"
    "        return true;\n"
)

SET_AP_OLD = """    if (!station_iface_->set_target_connect_ap_info(ap_info)) {
        return std::unexpected("Failed to set connect AP info: " + BROOKESIA_DESCRIBE_TO_STR(ap_info));
    }
    connecting_ap_info_ = {};
    connect_retries_ = 0;

    return {};
"""
SET_AP_FATAL = """    if (!add_connected_ap_info(ap_info)) {
        return std::unexpected("Failed to save connect AP info: " + BROOKESIA_DESCRIBE_TO_STR(ap_info));
    }
"""
SET_AP_WARN = """    if (!add_connected_ap_info(ap_info)) {
        BROOKESIA_LOGW("Failed to save connect AP info: %1%", BROOKESIA_DESCRIBE_TO_STR(ap_info));
    }
"""
SET_AP_NEW = """    if (!station_iface_->set_target_connect_ap_info(ap_info)) {
        return std::unexpected("Failed to set connect AP info: " + BROOKESIA_DESCRIBE_TO_STR(ap_info));
    }
    if (!add_connected_ap_info(ap_info)) {
        BROOKESIA_LOGW("Failed to save connect AP info: %1%", BROOKESIA_DESCRIBE_TO_STR(ap_info));
    }
    connecting_ap_info_ = {};
    connect_retries_ = 0;

    return {};
"""


def replace_once(path: Path, old: str, new: str) -> int:
    """Replace old with new if needed. 0 ok, 1 missing."""
    if not path.is_file():
        print(f"missing {path}")
        return 1
    text = path.read_text()
    if new in text:
        print(f"already patched {path.name}")
        return 0
    if old not in text:
        print(f"block not found in {path}")
        return 1
    path.write_text(text.replace(old, new, 1))
    print(f"patched {path}")
    return 0


def patch_set_connect_ap() -> int:
    """Seed SetConnectAp into Saved networks without failing the target set."""
    if not WIFI_CPP.is_file():
        print(f"missing {WIFI_CPP}")
        return 1
    text = WIFI_CPP.read_text()
    if SET_AP_NEW in text:
        print(f"already patched {WIFI_CPP.name}")
        return 0
    if SET_AP_FATAL in text:
        WIFI_CPP.write_text(text.replace(SET_AP_FATAL, SET_AP_WARN, 1))
        print(f"patched {WIFI_CPP}")
        return 0
    if SET_AP_OLD not in text:
        print(f"block not found in {WIFI_CPP}")
        return 1
    WIFI_CPP.write_text(text.replace(SET_AP_OLD, SET_AP_NEW, 1))
    print(f"patched {WIFI_CPP}")
    return 0


def main() -> int:
    """Apply Settings and Wi-Fi service patches. Return 0 on success."""
    status = replace_once(SETTINGS_CPP, RESERVE_OLD, RESERVE_NEW)
    status |= replace_once(WIFI_IPP, GUARD_OLD, GUARD_NEW)
    status |= replace_once(SERVICES_IPP, PREF_MISSING_OLD, PREF_MISSING_NEW)
    status |= replace_once(SERVICES_IPP, PREF_UNAVAIL_OLD, PREF_UNAVAIL_NEW)
    status |= replace_once(SERVICES_IPP, PREF_KEY_OLD, PREF_KEY_NEW)
    status |= patch_set_connect_ap()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
