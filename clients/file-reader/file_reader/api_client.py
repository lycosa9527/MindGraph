"""HTTP client for MindGraph file-reader (mgat + X-MG-Account + X-MG-Client)."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import requests as _requests
except ImportError:
    _requests = None

from file_reader.errors import AppError, ErrorCode, classify_http_error, classify_message, classify_network
from file_reader.server_url import normalize_server_url
from file_reader.settings import FileReaderSettings


@dataclass(frozen=True)
class IngestResult:
    """Outcome of a chat-handoff ingest call."""

    ok: bool
    error: Optional[AppError] = None
    document_id: Optional[int] = None


UploadResult = IngestResult


@dataclass(frozen=True)
class OrganizationProfile:
    """Organization block from GET /api/auth/me (matches web auth store)."""

    id: Optional[int]
    name: Optional[str]
    display_name: Optional[str]
    school_tier: Optional[str]


@dataclass(frozen=True)
class UserProfile:
    """Lightweight profile from GET /api/auth/me."""

    user_id: int
    name: str
    phone: str
    avatar: str
    organization: Optional[OrganizationProfile] = None


@dataclass(frozen=True)
class LiveSession:
    """Website pairing session waiting for file-reader upload."""

    code: str
    package_id: int
    package_name: str
    diagram_title: Optional[str]
    status: str
    expires_in_seconds: int


@dataclass(frozen=True)
class PackageItem:
    """Knowledge Space package row for the desktop picker."""

    id: int
    name: str
    diagram_id: Optional[str]
    source: Optional[str]
    status: str
    document_count: int
    completed_count: int


@dataclass(frozen=True)
class ConnectResult:
    """Outcome of connect (profile + optional packages)."""

    credentials_valid: bool
    profile: Optional[UserProfile]
    packages: List[PackageItem]
    error: Optional[AppError] = None

    @property
    def ok(self) -> bool:
        """True when profile and packages loaded successfully."""
        return self.credentials_valid and self.profile is not None and self.error is None


class FileReaderApiClient:
    """REST client for Document Summary packages and chat ingest."""

    def __init__(self, settings: FileReaderSettings) -> None:
        self._settings = settings

    def _base_url(self) -> str:
        return normalize_server_url(self._settings.server_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.api_token.strip()}",
            "X-MG-Account": self._settings.account_phone.strip(),
            "X-MG-Client": "file-reader",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Tuple[bool, Any, Optional[AppError]]:
        if not self._settings.api_token.strip() or not self._settings.account_phone.strip():
            return False, None, AppError(code=ErrorCode.MISSING_CREDENTIALS)
        url = f"{self._base_url()}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return True, {}, None
                try:
                    return True, json.loads(raw), None
                except json.JSONDecodeError:
                    return True, raw, None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            message = self._parse_error_message(detail) or str(exc)
            return False, None, classify_http_error(exc.code, message)
        except URLError as exc:
            return False, None, classify_network(str(exc.reason))

    @staticmethod
    def _parse_error_message(raw: str) -> str:
        if not raw:
            return ""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip()
        if isinstance(parsed, dict):
            detail = parsed.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list) and detail:
                first = detail[0]
                if isinstance(first, dict):
                    msg = first.get("msg")
                    if isinstance(msg, str):
                        return msg
        return raw.strip()

    @staticmethod
    def _parse_organization(data: dict) -> Optional[OrganizationProfile]:
        org = data.get("organization")
        if not isinstance(org, dict):
            return None
        org_id = org.get("id")
        parsed_id = int(org_id) if org_id is not None else None
        name_raw = org.get("name")
        name = str(name_raw).strip() if name_raw else None
        display_raw = org.get("display_name")
        display = str(display_raw).strip() if display_raw else None
        tier_raw = org.get("school_tier")
        tier = str(tier_raw).strip().lower() if tier_raw else None
        if parsed_id is None and not name and not display:
            return None
        return OrganizationProfile(
            id=parsed_id,
            name=name or None,
            display_name=display or None,
            school_tier=tier or None,
        )

    def fetch_profile(self) -> Tuple[bool, Optional[UserProfile], Optional[AppError]]:
        """Load the signed-in user profile."""
        ok, data, err = self._request_json("GET", "/api/auth/me")
        if not ok:
            return False, None, err or AppError(code=ErrorCode.PROFILE_FAILED)
        if not isinstance(data, dict):
            return False, None, AppError(code=ErrorCode.PROFILE_FAILED)
        name = str(data.get("name") or data.get("phone") or "User")
        phone = str(data.get("phone") or self._settings.account_phone)
        avatar = str(data.get("avatar") or "👤")
        user_id = int(data.get("id") or 0)
        organization = self._parse_organization(data)
        return (
            True,
            UserProfile(
                user_id=user_id,
                name=name,
                phone=phone,
                avatar=avatar,
                organization=organization,
            ),
            None,
        )

    def list_packages(self) -> Tuple[bool, List[PackageItem], Optional[AppError]]:
        """List Knowledge Space packages for the authenticated user."""
        ok, data, err = self._request_json("GET", "/api/doc-summary/packages")
        if not ok:
            return False, [], err or AppError(code=ErrorCode.PACKAGES_FAILED)
        if not isinstance(data, dict):
            return False, [], AppError(code=ErrorCode.PACKAGES_FAILED)
        rows = data.get("packages")
        if not isinstance(rows, list):
            return True, [], None
        items: List[PackageItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            items.append(
                PackageItem(
                    id=int(row.get("id") or 0),
                    name=str(row.get("name") or ""),
                    diagram_id=row.get("diagram_id"),
                    source=row.get("source"),
                    status=str(row.get("status") or "empty"),
                    document_count=int(row.get("document_count") or 0),
                    completed_count=int(row.get("completed_count") or 0),
                )
            )
        return True, items, None

    def list_waiting_sessions(self) -> Tuple[bool, List[LiveSession], Optional[AppError]]:
        """List pairing sessions the website is waiting on."""
        ok, data, err = self._request_json("GET", "/api/doc-summary/chat-handoff/waiting")
        if not ok:
            return False, [], err or AppError(code=ErrorCode.PACKAGES_FAILED)
        if not isinstance(data, dict):
            return False, [], AppError(code=ErrorCode.PACKAGES_FAILED)
        rows = data.get("sessions")
        if not isinstance(rows, list):
            return True, [], None
        items: List[LiveSession] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("package_name") or "").strip()
            diagram = str(row.get("diagram_title") or "").strip()
            items.append(
                LiveSession(
                    code=str(row.get("code") or ""),
                    package_id=int(row.get("package_id") or 0),
                    package_name=name,
                    diagram_title=diagram or None,
                    status=str(row.get("status") or "waiting"),
                    expires_in_seconds=int(row.get("expires_in_seconds") or 0),
                )
            )
        return True, items, None

    def connect(self) -> ConnectResult:
        """Verify credentials and load profile + packages."""
        ok, profile, err = self.fetch_profile()
        if not ok or profile is None:
            return ConnectResult(
                credentials_valid=False,
                profile=None,
                packages=[],
                error=err or AppError(code=ErrorCode.AUTH_FAILED),
            )
        ok_pkg, packages, err_pkg = self.list_packages()
        if not ok_pkg:
            mapped = err_pkg or AppError(code=ErrorCode.PACKAGES_FAILED)
            if mapped.code == ErrorCode.UNKNOWN and mapped.raw_detail:
                mapped = classify_message(mapped.raw_detail)
            return ConnectResult(
                credentials_valid=True,
                profile=profile,
                packages=[],
                error=mapped,
            )
        return ConnectResult(
            credentials_valid=True,
            profile=profile,
            packages=packages,
            error=None,
        )

    def start_handoff(self, package_id: int) -> Tuple[bool, Optional[str], Optional[AppError]]:
        """Mint a pairing code for the selected package."""
        ok, data, err = self._request_json(
            "POST",
            "/api/doc-summary/chat-handoff/start",
            {"package_id": package_id},
        )
        if not ok:
            return False, None, err or AppError(code=ErrorCode.PAIRING_FAILED)
        if not isinstance(data, dict):
            return False, None, AppError(code=ErrorCode.PAIRING_FAILED)
        code = data.get("code")
        if not isinstance(code, str) or len(code) != 6:
            return False, None, AppError(code=ErrorCode.PAIRING_FAILED, raw_detail="Invalid pairing response")
        return True, code, None

    def ingest_transcript(
        self,
        code: str,
        platform: str,
        chat_title: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        content: Optional[str] = None,
        source_export_name: Optional[str] = None,
    ) -> IngestResult:
        """POST chat-handoff ingest with pairing code."""
        payload: Dict[str, Any] = {
            "code": code.strip(),
            "platform": platform,
            "chat_title": chat_title.strip() or "Chat export",
        }
        if messages:
            payload["messages"] = messages
        elif content:
            payload["content"] = content
        else:
            return IngestResult(False, AppError(code=ErrorCode.NO_CONTENT))
        if source_export_name:
            payload["source_export_name"] = source_export_name.strip()

        ok, data, err = self._request_json(
            "POST",
            "/api/doc-summary/chat-handoff/ingest",
            payload,
            timeout=120,
        )
        if not ok:
            return IngestResult(False, err or AppError(code=ErrorCode.UPLOAD_FAILED))
        doc_id: Optional[int] = None
        if isinstance(data, dict) and data.get("id") is not None:
            doc_id = int(data["id"])
        return IngestResult(True, document_id=doc_id)

    def upload_package_document(self, package_id: int, file_path: Path) -> UploadResult:
        """Upload a local file into a Knowledge Space package."""
        if _requests is None:
            return UploadResult(False, AppError(code=ErrorCode.UPLOAD_FAILED, raw_detail="requests not installed"))
        if not self._settings.api_token.strip() or not self._settings.account_phone.strip():
            return UploadResult(False, AppError(code=ErrorCode.MISSING_CREDENTIALS))
        if not file_path.is_file():
            return UploadResult(False, AppError(code=ErrorCode.UPLOAD_FAILED, raw_detail="File not found"))

        url = f"{self._base_url()}/api/doc-summary/packages/{package_id}/documents/upload"
        headers = {
            "Authorization": f"Bearer {self._settings.api_token.strip()}",
            "X-MG-Account": self._settings.account_phone.strip(),
            "X-MG-Client": "file-reader",
            "Accept": "application/json",
        }
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        try:
            with file_path.open("rb") as handle:
                response = _requests.post(
                    url,
                    headers=headers,
                    files={"file": (file_path.name, handle, mime_type)},
                    timeout=120,
                )
        except _requests.RequestException as exc:
            return UploadResult(False, classify_network(str(exc)))

        if response.status_code >= 400:
            message = self._parse_error_message(response.text) or response.reason
            return UploadResult(False, classify_http_error(response.status_code, message))

        doc_id: Optional[int] = None
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("id") is not None:
            doc_id = int(data["id"])
        return UploadResult(True, document_id=doc_id)
