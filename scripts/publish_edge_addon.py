"""Publish MindGraph extension updates to Microsoft Edge Add-ons (REST API v1.1)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from utils.extension_store_packaging import build_store_zip

_DEFAULT_API_BASE = "https://api.addons.microsoftedge.microsoft.com"
_DEFAULT_RETRY_LIMIT = 60
_DEFAULT_RETRY_SECONDS = 5
_TERMINAL_STATUSES = frozenset({"Succeeded", "Failed"})
_IN_REVIEW_ERROR = "InProgressSubmission"


class EdgeAddonPublishError(RuntimeError):
    """Raised when Edge Add-ons API publish flow fails."""


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EdgeAddonPublishError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _auth_headers(client_id: str, api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"ApiKey {api_key}",
        "X-ClientID": client_id,
    }


def _operation_id_from_location(location: str) -> str:
    trimmed = location.strip()
    if not trimmed:
        raise EdgeAddonPublishError("Empty Location header in API response")
    path = urlparse(trimmed).path if "://" in trimmed else trimmed
    operation_id = path.rstrip("/").split("/")[-1]
    if not operation_id:
        raise EdgeAddonPublishError(f"Could not parse operation id from Location: {location!r}")
    return operation_id


def _request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=body, method=method)
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EdgeAddonPublishError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise EdgeAddonPublishError(f"{method} {url} failed: {exc}") from exc


def _parse_status_payload(payload: bytes) -> dict[str, Any]:
    if not payload:
        return {}
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise EdgeAddonPublishError(f"Invalid JSON from API: {payload!r}") from exc
    if not isinstance(parsed, dict):
        raise EdgeAddonPublishError(f"Unexpected JSON payload type: {type(parsed)!r}")
    return parsed


def _failure_hint(error_code: str) -> str:
    if error_code == _IN_REVIEW_ERROR:
        return (
            " Extension is under review — package manually via Partner Center or "
            "chrome-extension/scripts/manual_push_edge.sh; do not API-publish yet."
        )
    return ""


def _wait_for_operation(
    *,
    status_url: str,
    headers: dict[str, str],
    label: str,
    retry_limit: int,
    retry_seconds: int,
) -> dict[str, Any]:
    for attempt in range(1, retry_limit + 1):
        status_code, _, payload = _request("GET", status_url, headers)
        body = _parse_status_payload(payload)
        status = str(body.get("status", ""))
        message = body.get("message")
        print(f"[{label}] attempt {attempt}/{retry_limit}: HTTP {status_code}, status={status}")
        if message:
            print(f"[{label}] message: {message}")
        if status in _TERMINAL_STATUSES:
            if status != "Succeeded":
                errors = body.get("errors")
                error_code = str(body.get("errorCode", ""))
                raise EdgeAddonPublishError(
                    f"{label} failed: {message or status}; errors={errors!r}.{_failure_hint(error_code)}"
                )
            return body
        time.sleep(retry_seconds)
    raise EdgeAddonPublishError(f"{label} timed out after {retry_limit} attempts")


def upload_package(
    *,
    api_base: str,
    product_id: str,
    client_id: str,
    api_key: str,
    zip_path: Path,
    retry_limit: int,
    retry_seconds: int,
) -> None:
    """Upload zip to draft submission and wait until processing succeeds."""
    upload_url = f"{api_base}/v1/products/{product_id}/submissions/draft/package"
    headers = _auth_headers(client_id, api_key)
    headers["Content-Type"] = "application/zip"
    zip_bytes = zip_path.read_bytes()
    print(f"Uploading {zip_path} ({len(zip_bytes)} bytes) …")
    status_code, response_headers, _ = _request("POST", upload_url, headers, zip_bytes)
    if status_code != 202:
        raise EdgeAddonPublishError(f"Upload expected HTTP 202, got {status_code}")
    location = response_headers.get("location", "")
    operation_id = _operation_id_from_location(location)
    status_url = f"{api_base}/v1/products/{product_id}/submissions/draft/package/operations/{operation_id}"
    _wait_for_operation(
        status_url=status_url,
        headers=_auth_headers(client_id, api_key),
        label="upload",
        retry_limit=retry_limit,
        retry_seconds=retry_seconds,
    )


def publish_submission(
    *,
    api_base: str,
    product_id: str,
    client_id: str,
    api_key: str,
    notes: str,
    retry_limit: int,
    retry_seconds: int,
) -> None:
    """Submit draft for certification review and wait until publish succeeds."""
    publish_url = f"{api_base}/v1/products/{product_id}/submissions"
    headers = _auth_headers(client_id, api_key)
    headers["Content-Type"] = "application/json"
    body = json.dumps({"notes": notes}, ensure_ascii=False).encode("utf-8")
    print("Submitting draft for certification …")
    status_code, response_headers, _ = _request("POST", publish_url, headers, body)
    if status_code != 202:
        raise EdgeAddonPublishError(f"Publish expected HTTP 202, got {status_code}")
    location = response_headers.get("location", "")
    operation_id = _operation_id_from_location(location)
    status_url = f"{api_base}/v1/products/{product_id}/submissions/operations/{operation_id}"
    result = _wait_for_operation(
        status_url=status_url,
        headers=_auth_headers(client_id, api_key),
        label="publish",
        retry_limit=retry_limit,
        retry_seconds=retry_seconds,
    )
    print(f"Publish succeeded: {result.get('message', 'ok')}")


def _load_notes(notes_file: Path | None) -> str:
    if notes_file is not None:
        return notes_file.read_text(encoding="utf-8").strip()
    inline = os.environ.get("EDGE_ADDON_PUBLISH_NOTES", "").strip()
    if inline:
        return inline
    raise EdgeAddonPublishError("Certification notes required: set EDGE_ADDON_PUBLISH_NOTES or pass --notes-file")


def main() -> None:
    """CLI entry: package, upload, and publish extension to Edge Add-ons."""
    parser = argparse.ArgumentParser(
        description="Package and publish MindGraph extension to Microsoft Edge Add-ons (API v1.1).",
    )
    parser.add_argument(
        "--package-only",
        action="store_true",
        help="Only build the store zip; do not call Edge Add-ons API.",
    )
    parser.add_argument(
        "--upload-only",
        action="store_true",
        help="Upload package to draft submission but do not publish for review.",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        help="Use an existing zip instead of building a new one.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path when building a new zip (see package_extension.py).",
    )
    parser.add_argument(
        "--notes-file",
        type=Path,
        help="Certification notes for reviewers (<2000 chars).",
    )
    args = parser.parse_args()

    zip_path = args.zip
    if zip_path is None:
        zip_path = build_store_zip(args.output)
        print(f"Packaged {zip_path}")

    if args.package_only:
        return

    client_id = _env("EDGE_ADDON_CLIENT_ID")
    api_key = _env("EDGE_ADDON_API_KEY")
    product_id = _env("EDGE_ADDON_PRODUCT_ID")
    api_base = _optional_env("EDGE_ADDON_API_BASE", _DEFAULT_API_BASE).rstrip("/")
    retry_limit = int(_optional_env("EDGE_ADDON_RETRY_LIMIT", str(_DEFAULT_RETRY_LIMIT)))
    retry_seconds = int(_optional_env("EDGE_ADDON_RETRY_SECONDS", str(_DEFAULT_RETRY_SECONDS)))

    upload_package(
        api_base=api_base,
        product_id=product_id,
        client_id=client_id,
        api_key=api_key,
        zip_path=zip_path,
        retry_limit=retry_limit,
        retry_seconds=retry_seconds,
    )
    print("Package upload complete.")

    if args.upload_only:
        return

    notes = _load_notes(args.notes_file)
    if len(notes) > 2000:
        raise EdgeAddonPublishError(f"Certification notes are {len(notes)} characters; Microsoft limit is 2000.")

    publish_submission(
        api_base=api_base,
        product_id=product_id,
        client_id=client_id,
        api_key=api_key,
        notes=notes,
        retry_limit=retry_limit,
        retry_seconds=retry_seconds,
    )


if __name__ == "__main__":
    try:
        main()
    except EdgeAddonPublishError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
