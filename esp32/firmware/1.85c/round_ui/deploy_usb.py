"""Push staged 360 overlay JSON to the board over Brookesia USB Storage."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from brookesia_usb_cli.cli import UsbClient, _serial_module

PORT = "COM5"
LITTLEFS = Path(r"C:\Users\roywa\Desktop\MindGraph-1.85C-flash\round_overlay")
HOST_TO_DEVICE = (
    ("system/super/themes/font/360.json", "/littlefs/system/super/themes/font/360.json"),
    ("system/super/themes/size/360.json", "/littlefs/system/super/themes/size/360.json"),
    ("system/super/shell/constants/360.json", "/littlefs/system/super/shell/constants/360.json"),
    ("system/super/themes/light.json", "/littlefs/system/super/themes/light.json"),
    ("system/super/themes/dark.json", "/littlefs/system/super/themes/dark.json"),
    ("system/super/shell/root.json", "/littlefs/system/super/shell/root.json"),
    (
        "apps/brookesia.general.settings/res/constants/360.json",
        "/littlefs/apps/brookesia.general.settings/res/constants/360.json",
    ),
    (
        "apps/brookesia.general.settings/res/root.json",
        "/littlefs/apps/brookesia.general.settings/res/root.json",
    ),
)


def read_json_skip_noise(self) -> dict:
    while True:
        line = self.serial.readline()
        if not line:
            raise TimeoutError("timed out waiting for device response")
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value


def mkdir_p(client: UsbClient, path: str) -> None:
    current = ""
    for part in path.strip("/").split("/"):
        current += "/" + part
        try:
            client.call("Storage", "FSMkdir", {"Path": current})
        except RuntimeError:
            pass


def main() -> int:
    UsbClient.read_json = read_json_skip_noise
    with UsbClient(PORT, 115200, 30.0) as client:
        client.hello()
        for relative, remote in HOST_TO_DEVICE:
            host = LITTLEFS / relative
            text = host.read_text(encoding="utf-8")
            mkdir_p(client, str(Path(remote).parent).replace("\\", "/"))
            client.call("Storage", "FSWriteText", {"Path": remote, "Data": text})
            print(f"wrote {remote} ({len(text)} bytes)")
    print("resetting")
    serial, _ = _serial_module()
    with serial.Serial(PORT, 115200, timeout=1) as port:
        port.dtr = False
        port.rts = True
        time.sleep(0.1)
        port.rts = False
    time.sleep(22)
    with UsbClient(PORT, 115200, 40.0) as client:
        hello = client.hello()
        print(json.dumps(hello, indent=2))
    print("round overlay deployed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        print(f"deploy_usb: {error}", file=sys.stderr)
        raise SystemExit(1)
