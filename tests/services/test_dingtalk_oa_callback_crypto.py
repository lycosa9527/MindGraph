"""Tests for DingTalk open-platform callback crypto (official SDK vectors)."""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.oa_callback_crypto import DingTalkOaCallbackCrypto


def test_roundtrip_encrypt_decrypt() -> None:
    crypto = DingTalkOaCallbackCrypto(
        "mryue",
        "Yue0EfdN5900c1ce5cf6A152c63DDe1808a60c5ecd7",
        "ding6ccabc44d2c8d38b",
    )
    expect = '{"EventType":"check_url"}'
    payload = crypto.get_encrypted_map(expect)
    plain = crypto.get_decrypt_msg(
        payload["msg_signature"],
        payload["timeStamp"],
        payload["nonce"],
        payload["encrypt"],
    )
    assert plain == expect


def test_official_sample_decrypt_vector() -> None:
    """Vector from DingCallbackCrypto3.py __main__ block."""
    crypto = DingTalkOaCallbackCrypto(
        "mryue",
        "Yue0EfdN5900c1ce5cf6A152c63DDe1808a60c5ecd7",
        "ding6ccabc44d2c8d38b",
    )
    plain = crypto.get_decrypt_msg(
        "03044561471240d4a14bb09372dfcfd4fd0e40cb",
        "1608001896814",
        "WL4PK6yA",
        "0vJiX6vliEpwG3U45CtXqi+m8PXbQRARJ8p8BbDuD1EMTDf0jKpQ79QS93qEk7XHpP6u+oTTrd15NRPvNvmBKyDCYxxOK+HZeKju4yhELOFchzNukR+t8SB/qk4ROMu3",
    )
    assert plain == '{"EventType":"check_url"}'


def test_success_encrypted_map_keys() -> None:
    crypto = DingTalkOaCallbackCrypto("t", "Yue0EfdN5900c1ce5cf6A152c63DDe1808a60c5ecd7", "ding6ccabc44d2c8d38b")
    out = crypto.get_encrypted_map("success")
    assert set(out.keys()) == {"msg_signature", "encrypt", "timeStamp", "nonce"}
    assert isinstance(out["encrypt"], str) and out["encrypt"].strip()
