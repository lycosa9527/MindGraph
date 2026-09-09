#!/usr/bin/env python3
"""Copy 360x360 round overlays and append Super/Settings theme variants."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from patch_super_keyboard import apply_keyboard_patches
from patch_super_launcher import patch_launcher_cpp

ROUND_WHEN = "${expr(${env.widthDp} == 360dp && ${env.heightDp} == 360dp)}"
THEME_ASSETS = ["font/360.json", "size/360.json"]
SHELL_ASSETS = ["constants/360.json"]
SETTINGS_ASSETS = ["constants/360.json"]
FILES_ASSETS = ["constants/360.json"]
APP_STORE_ASSETS = ["constants/360.json"]
SETTINGS_ROW_TEMPLATES = (
    "templates/nav_menu_item.json",
    "templates/menu_item.json",
    "templates/setting_row.json",
    "templates/switch_row.json",
)


def load_json(path: Path) -> dict:
    """Read a UTF-8 JSON object from path."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    """Write a JSON object with trailing newline."""
    path.write_text(json.dumps(value, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_variant(document: dict, assets: list[str]) -> bool:
    """Attach or refresh the 360x360 asset variant. True when the document changed."""
    variants = document.setdefault("variants", [])
    for variant in variants:
        if variant.get("when") == ROUND_WHEN:
            if variant.get("assets") != assets:
                variant["assets"] = assets
                return True
            return False
    variants.append({"when": ROUND_WHEN, "assets": assets})
    return True


def copy_tree(src: Path, dest: Path) -> None:
    """Copy a file or directory tree onto dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return
    shutil.copy2(src, dest)


def find_by_id(node: dict, target: str) -> dict | None:
    """Return the first descendant whose id matches target."""
    if node.get("id") == target:
        return node
    for child in node.get("children", []):
        if isinstance(child, dict):
            found = find_by_id(child, target)
            if found is not None:
                return found
    return None


def patch_round_status_bar(super_root: Path) -> None:
    """Wear-style 12 o'clock capsule: Wi-Fi + clock sit in the circle, not the corners."""
    overlay_path = super_root / "shell" / "screens" / "overlay.json"
    document = load_json(overlay_path)
    status = find_by_id(document, "status")
    if status is None:
        raise RuntimeError("round_ui: overlay.json is missing status")
    status.setdefault("layout", {})
    status["layout"]["mainAlign"] = "center"
    status.setdefault("placement", {})
    status["placement"]["x"] = (
        "${expr((${env.widthDp} - ${constant.ui.overlay.metric.statusClusterWidth}) / 2)}"
    )
    status["placement"]["width"] = "${constant.ui.overlay.metric.statusClusterWidth}"
    status_right = find_by_id(status, "status_right")
    if status_right is None:
        raise RuntimeError("round_ui: overlay.json is missing status_right")
    status_right.setdefault("layout", {})
    status_right["layout"]["mainAlign"] = "center"
    status_right.setdefault("placement", {})
    status_right["placement"]["width"] = "match"
    bindings = status.get("bindings")
    if isinstance(bindings, dict):
        bindings.pop("placement.y", None)
        if not bindings:
            status.pop("bindings", None)
    save_json(overlay_path, document)

    style_path = super_root / "shell" / "styles" / "shell.json"
    styles = load_json(style_path)
    status_bar = styles.setdefault("styles", {}).setdefault("shell.statusBar", {})
    status_bar["radius"] = "16dp"
    status_bar["opacity"] = 230
    save_json(style_path, styles)


def patch_keyboard_composer(super_root: Path) -> None:
    """Make the typed field a visible box sitting on the 九宫格."""
    style_path = super_root / "shell" / "styles" / "shell.json"
    if not style_path.is_file():
        return
    styles = load_json(style_path)
    bucket = styles.setdefault("styles", {})
    keyboard_input = bucket.setdefault("shell.keyboardInput", {})
    keyboard_input["borderWidth"] = "2dp"
    keyboard_input["radius"] = "12dp"
    keyboard_field = bucket.setdefault("shell.keyboardInputField", {})
    keyboard_field["borderWidth"] = "2dp"
    keyboard_field["radius"] = "10dp"
    save_json(style_path, styles)


def patch_launcher_labels(super_root: Path) -> None:
    """Keep launcher names on one ellipsized line inside the circle."""
    path = super_root / "shell" / "templates" / "launcher_app_button.json"
    if not path.is_file():
        return
    document = load_json(path)
    node = document.get("node", document)
    app_name = find_by_id(node, "app_name")
    if app_name is None:
        return
    app_name.setdefault("style", {})
    app_name["style"]["textOverflow"] = "ellipsis"
    app_name["style"]["textAlign"] = "center"
    save_json(path, document)


def patch_launcher_frame(super_root: Path) -> None:
    """Inset the launcher content band to the circular safe area."""
    path = super_root / "shell" / "screens" / "app_launcher.json"
    if not path.is_file():
        return
    document = load_json(path)
    content = find_by_id(document, "content")
    if content is None:
        return
    content.setdefault("placement", {})
    content["placement"]["x"] = "${constant.ui.content.metric.x}"
    content["placement"]["width"] = "${constant.ui.content.metric.width}"
    content["placement"]["height"] = "${constant.ui.content.metric.height}"
    save_json(path, document)


def patch_message_dialog_actions(super_root: Path) -> None:
    """Stack dialog actions so two buttons fit the watch width."""
    path = super_root / "shell" / "screens" / "message_dialog.json"
    if not path.is_file():
        return
    document = load_json(path)
    actions = find_by_id(document, "actions")
    if actions is None:
        return
    actions.setdefault("layout", {})
    actions["layout"]["flexFlow"] = "column"
    save_json(path, document)


def patch_debug_panel(super_root: Path) -> None:
    """Park the debug panel inside the inscribed content square."""
    overlay_path = super_root / "shell" / "screens" / "overlay.json"
    document = load_json(overlay_path)
    debug = find_by_id(document, "debug_panel")
    if debug is None:
        return
    debug.setdefault("placement", {})
    debug["placement"]["mode"] = "absolute"
    debug["placement"]["align"] = "topLeft"
    debug["placement"]["x"] = "56dp"
    debug["placement"]["y"] = "72dp"
    debug["placement"]["width"] = "248dp"
    save_json(overlay_path, document)


def patch_settings_header(settings_res: Path) -> None:
    """Drop Settings header padding and pin it under the status capsule."""
    path = settings_res / "screens" / "header.json"
    if not path.is_file():
        return
    document = load_json(path)
    document.setdefault("style", {})
    document["style"]["paddingTop"] = "0dp"
    header_bar = find_by_id(document, "bar")
    if header_bar is None:
        raise RuntimeError("round_ui: settings header is missing bar")
    header_bar.setdefault("style", {})
    header_bar["style"]["paddingLeft"] = "4dp"
    header_bar["style"]["paddingRight"] = "4dp"
    header_bar["style"]["paddingTop"] = "4dp"
    header_bar["style"]["paddingBottom"] = "4dp"
    header_bar.setdefault("placement", {})
    header_bar["placement"]["x"] = "${constant.settings.layout.pageX}"
    header_bar["placement"]["y"] = "${constant.settings.layout.headerY}"
    header_bar["placement"]["width"] = "${constant.settings.layout.pageWidth}"
    save_json(path, document)


def patch_files_header(files_res: Path) -> None:
    """Lift the Files header below the 12 o'clock capsule."""
    path = files_res / "screens" / "header.json"
    if not path.is_file():
        return
    document = load_json(path)
    header_bar = find_by_id(document, "bar")
    if header_bar is None:
        return
    header_bar.setdefault("placement", {})
    header_bar["placement"]["y"] = "${constant.files.layout.headerY}"
    save_json(path, document)


def patch_app_store_padding(store_res: Path) -> None:
    """Inset App Store padding so list cards stay on the disc."""
    path = store_res / "screens" / "app_store.json"
    if not path.is_file():
        return
    document = load_json(path)
    style = document.setdefault("style", {})
    pad = "${constant.appStore.layout.pagePadding}"
    style["paddingLeft"] = pad
    style["paddingRight"] = pad
    style["paddingBottom"] = pad
    style["paddingTop"] = "72dp"
    style.pop("padding", None)
    save_json(path, document)


def patch_settings_row_gaps(settings_res: Path) -> None:
    """Tighten Settings rows and ellipsize titles that hit the bezel."""
    for relative in SETTINGS_ROW_TEMPLATES:
        path = settings_res / relative
        if not path.is_file():
            continue
        document = load_json(path)
        node = document.get("node", document)
        node.setdefault("layout", {})
        node["layout"]["gap"] = "6dp"
        title = find_by_id(node, "title")
        if title is not None:
            title.setdefault("style", {})
            title["style"]["textOverflow"] = "ellipsis"
            title["style"]["textAlign"] = "center"
            title.setdefault("placement", {})
            title["placement"]["width"] = "match"
        if document.get("id") == "switch_row":
            node.setdefault("placement", {})
            node["placement"]["height"] = "${constant.settings.layout.rowHeight}"
        save_json(path, document)


def patch_settings_display(settings_res: Path) -> None:
    """Stack theme-mode cards so they do not overflow the circle."""
    path = settings_res / "screens" / "display.json"
    if not path.is_file():
        return
    document = load_json(path)
    theme_modes = find_by_id(document, "theme_modes")
    if theme_modes is None:
        return
    theme_modes.setdefault("layout", {})
    theme_modes["layout"]["flexFlow"] = "column"
    save_json(path, document)


def patch_wifi_connect_actions(settings_res: Path) -> None:
    """Stack Wi-Fi connect actions for the 360-wide safe band."""
    path = settings_res / "screens" / "wifi_connect.json"
    if not path.is_file():
        return
    document = load_json(path)
    actions = find_by_id(document, "actions")
    if actions is None:
        return
    actions.setdefault("layout", {})
    actions["layout"]["flexFlow"] = "column"
    actions["layout"]["mainAlign"] = "center"
    save_json(path, document)


def apply_app_overlay(res_dir: Path, overlay_dir: Path, assets: list[str]) -> bool:
    """Copy an app overlay and register its 360 variant. True when root.json changed."""
    if overlay_dir.exists() and res_dir.exists():
        copy_tree(overlay_dir, res_dir)
    root = res_dir / "root.json"
    if not root.is_file():
        return False
    document = load_json(root)
    changed = ensure_variant(document, assets)
    save_json(root, document)
    return changed


def apply(littlefs: Path, overlay: Path) -> None:
    """Copy overlays, patch Super/Settings, and register 360 variants."""
    super_root = littlefs / "system" / "super"
    settings_res = littlefs / "apps" / "brookesia.general.settings" / "res"
    files_res = littlefs / "apps" / "brookesia.general.files" / "res"
    store_res = littlefs / "apps" / "brookesia.general.app_store" / "res"
    copy_tree(overlay / "super", super_root)
    if (overlay / "settings").exists() and settings_res.exists():
        copy_tree(overlay / "settings", settings_res)
    patch_round_status_bar(super_root)
    patch_keyboard_composer(super_root)
    patch_launcher_frame(super_root)
    patch_launcher_labels(super_root)
    patch_message_dialog_actions(super_root)
    patch_debug_panel(super_root)
    if settings_res.exists():
        patch_settings_header(settings_res)
        patch_settings_row_gaps(settings_res)
        patch_settings_display(settings_res)
        patch_wifi_connect_actions(settings_res)

    changed = False
    for name in ("light.json", "dark.json"):
        path = super_root / "themes" / name
        document = load_json(path)
        changed = ensure_variant(document, THEME_ASSETS) or changed
        save_json(path, document)

    shell_root = super_root / "shell" / "root.json"
    document = load_json(shell_root)
    changed = ensure_variant(document, SHELL_ASSETS) or changed
    save_json(shell_root, document)

    if settings_res.is_dir():
        changed = apply_app_overlay(settings_res, overlay / "settings", SETTINGS_ASSETS) or changed
    if files_res.is_dir():
        changed = apply_app_overlay(files_res, overlay / "files", FILES_ASSETS) or changed
        patch_files_header(files_res)
    if store_res.is_dir():
        changed = apply_app_overlay(store_res, overlay / "app_store", APP_STORE_ASSETS) or changed
        patch_app_store_padding(store_res)

    launcher_cpp = littlefs.parent / "managed_components" / "espressif__brookesia_system_super" / "src" / "shell_app_launcher.cpp"
    if launcher_cpp.is_file():
        launcher_changed = patch_launcher_cpp(launcher_cpp)
        print(f"round_ui: launcher grid ({launcher_changed})")
    motion_changed, password_changed = apply_keyboard_patches()
    print(f"round_ui: keyboard motion={motion_changed} password={password_changed}")

    print(f"round_ui: applied to {littlefs} (variants_changed={changed})")


def main() -> int:
    """CLI entry: --littlefs and --overlay paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--littlefs", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    args = parser.parse_args()
    apply(args.littlefs.resolve(), args.overlay.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
