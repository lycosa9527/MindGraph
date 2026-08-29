"""
Load Alipay certificate-mode material (app cert + Alipay cert + root cert).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


@dataclass(frozen=True)
class AlipayCertMaterial:
    """Converted keys and certificate serials for the official Python SDK."""

    app_private_key_pkcs1: str
    alipay_public_key: str
    app_cert_sn: str
    alipay_root_cert_sn: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_pem_certificates(pem_text: str) -> list[x509.Certificate]:
    """Parse one or more PEM certificates from a file body."""
    certs: list[x509.Certificate] = []
    for chunk in pem_text.split("-----END CERTIFICATE-----"):
        body = chunk.strip()
        if "BEGIN CERTIFICATE" not in body:
            continue
        pem = f"{body}\n-----END CERTIFICATE-----\n"
        certs.append(x509.load_pem_x509_certificate(pem.encode("utf-8")))
    return certs


def certificate_sn(cert: x509.Certificate) -> str:
    """Alipay app/public cert SN: MD5(issuer RFC4514 + serial)."""
    payload = f"{cert.issuer.rfc4514_string()}{cert.serial_number}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def root_certificate_sn(certs: list[x509.Certificate]) -> str:
    """Join RSA-signed cert SNs in the Alipay root bundle with ``_``."""
    serials: list[str] = []
    for cert in certs:
        oid = cert.signature_algorithm_oid.dotted_string
        if oid.startswith("1.2.840.113549.1.1"):
            serials.append(certificate_sn(cert))
    return "_".join(serials)


def _wrap_oneline_pkcs8(raw: str) -> str:
    if "BEGIN" in raw:
        return raw
    body = "".join(raw.split())
    wrapped = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN PRIVATE KEY-----\n{wrapped}\n-----END PRIVATE KEY-----"


def load_rsa_private_key(raw: str) -> RSAPrivateKey:
    """Load PKCS#8 (key-tool one-liner) or PEM PKCS#1 app private key."""
    pem = _wrap_oneline_pkcs8(raw.strip().replace("\r\n", "\n"))
    loaded = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(loaded, RSAPrivateKey):
        raise ValueError("Alipay app private key is not RSA")
    return loaded


def pkcs1_one_line(private_key: RSAPrivateKey) -> str:
    """SDK ``sign_with_rsa2`` requires PKCS#1 without PEM markers."""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return "".join(line.strip() for line in pem.splitlines() if "BEGIN" not in line and "END" not in line)


def public_key_one_line(public_key: RSAPublicKey) -> str:
    """SubjectPublicKeyInfo body for SDK verify / notify RSA2."""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return "".join(line.strip() for line in pem.splitlines() if "BEGIN" not in line and "END" not in line)


def _private_key_path(cert_dir: Path) -> Path | None:
    matches = list(cert_dir.glob("应用私钥*.txt"))
    if matches:
        return matches[0]
    english = cert_dir / "app_private_key.txt"
    if english.is_file():
        return english
    return None


def discover_cert_paths(cert_dir: Path, app_id: str) -> tuple[Path, Path, Path, Path]:
    """Resolve the four files the official key tool writes into one folder."""
    private_path = _private_key_path(cert_dir)
    if private_path is None:
        raise FileNotFoundError(f"no 应用私钥*.txt or app_private_key.txt in {cert_dir}")
    app_cert = cert_dir / f"appCertPublicKey_{app_id}.crt"
    alipay_cert = cert_dir / "alipayCertPublicKey_RSA2.crt"
    root_cert = cert_dir / "alipayRootCert.crt"
    if not app_cert.is_file() or not alipay_cert.is_file() or not root_cert.is_file():
        raise FileNotFoundError(f"missing app/alipay/root cert in {cert_dir}")
    return private_path, app_cert, alipay_cert, root_cert


def cert_bundle_present(cert_dir: Path, app_id: str) -> bool:
    """True when the upload folder has the private key and three cert PEMs."""
    if not cert_dir.is_dir():
        return False
    try:
        discover_cert_paths(cert_dir, app_id)
    except FileNotFoundError:
        return False
    return True


def load_cert_material(
    *,
    private_key_text: str,
    app_cert_text: str,
    alipay_cert_text: str,
    root_cert_text: str,
) -> AlipayCertMaterial:
    """Validate the private key against the app cert and return SDK material."""
    private_key = load_rsa_private_key(private_key_text)
    app_certs = load_pem_certificates(app_cert_text)
    alipay_certs = load_pem_certificates(alipay_cert_text)
    root_certs = load_pem_certificates(root_cert_text)
    if not app_certs or not alipay_certs or not root_certs:
        raise ValueError("Alipay certificate PEM is empty or invalid")
    app_cert = app_certs[0]
    alipay_cert = alipay_certs[0]
    app_pub = app_cert.public_key()
    alipay_pub = alipay_cert.public_key()
    if not isinstance(app_pub, RSAPublicKey) or not isinstance(alipay_pub, RSAPublicKey):
        raise ValueError("Alipay certificates must contain RSA keys")
    if public_key_one_line(private_key.public_key()) != public_key_one_line(app_pub):
        raise ValueError("Alipay private key does not match appCertPublicKey")
    return AlipayCertMaterial(
        app_private_key_pkcs1=pkcs1_one_line(private_key),
        alipay_public_key=public_key_one_line(alipay_pub),
        app_cert_sn=certificate_sn(app_cert),
        alipay_root_cert_sn=root_certificate_sn(root_certs),
    )


def load_cert_material_from_dir(cert_dir: Path, app_id: str) -> AlipayCertMaterial:
    """Load the key-tool output directory for ``app_id``."""
    private_path, app_cert_path, alipay_cert_path, root_cert_path = discover_cert_paths(cert_dir, app_id)
    return load_cert_material(
        private_key_text=_read_text(private_path),
        app_cert_text=_read_text(app_cert_path),
        alipay_cert_text=_read_text(alipay_cert_path),
        root_cert_text=_read_text(root_cert_path),
    )
