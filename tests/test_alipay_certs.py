"""Unit tests for Alipay certificate-mode key loading."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from services.markets.alipay_certs import (
    cert_bundle_present,
    load_cert_material,
    load_rsa_private_key,
    pkcs1_one_line,
)
from services.markets.alipay_settings import DEFAULT_ALIPAY_CERT_DIR, resolve_alipay_cert_dir


def _self_signed(key: rsa.RSAPrivateKey, common_name: str) -> x509.Certificate:
    """Build a short-lived self-signed RSA cert for tests."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(123456789)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )


def _pem_cert(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def test_pkcs8_oneline_converts_for_official_sdk() -> None:
    """Test pkcs8 oneline converts for official sdk."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pkcs8 = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    oneline = "".join(line.strip() for line in pkcs8.splitlines() if "BEGIN" not in line and "END" not in line)
    loaded = load_rsa_private_key(oneline)
    pkcs1 = pkcs1_one_line(loaded)
    assert "BEGIN" not in pkcs1
    assert pkcs1.startswith("MII")


def test_load_cert_material_rejects_mismatched_private_key() -> None:
    """Test load cert material rejects mismatched private key."""
    app_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alipay_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app_cert = _self_signed(app_key, "app")
    alipay_cert = _self_signed(alipay_key, "alipay")
    with pytest.raises(ValueError, match="does not match"):
        load_cert_material(
            private_key_text=other_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("ascii"),
            app_cert_text=_pem_cert(app_cert),
            alipay_cert_text=_pem_cert(alipay_cert),
            root_cert_text=_pem_cert(alipay_cert),
        )


def test_load_cert_material_round_trip() -> None:
    """Test load cert material round trip."""
    app_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alipay_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app_cert = _self_signed(app_key, "app")
    alipay_cert = _self_signed(alipay_key, "alipay")
    material = load_cert_material(
        private_key_text=app_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii"),
        app_cert_text=_pem_cert(app_cert),
        alipay_cert_text=_pem_cert(alipay_cert),
        root_cert_text=_pem_cert(alipay_cert),
    )
    assert material.app_cert_sn
    assert material.alipay_root_cert_sn
    assert material.alipay_public_key.startswith("MII")
    assert material.app_private_key_pkcs1.startswith("MII")


def test_empty_cert_dir_is_not_ready(tmp_path) -> None:
    """Test empty cert dir is not ready."""
    assert cert_bundle_present(tmp_path, "2021000000000000") is False


def test_default_cert_dir_is_repo_data_folder(monkeypatch) -> None:
    """Test default cert dir is repo data folder."""
    monkeypatch.delenv("ALIPAY_CERT_DIR", raising=False)
    assert DEFAULT_ALIPAY_CERT_DIR == "data/alipay-certs"
    assert resolve_alipay_cert_dir() == Path(DEFAULT_ALIPAY_CERT_DIR)
