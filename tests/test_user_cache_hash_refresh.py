"""Redis user hashes missing newer preference fields must reload from the database."""

from services.redis.cache.redis_user_cache import user_cache_hash_needs_refresh


def test_missing_bilingual_field_refreshes_any_role() -> None:
    """A pre-bilingual hash must not deserialize as bilingual off."""
    stale = {"id": "7", "role": "teacher", "ui_language": "zh"}
    assert user_cache_hash_needs_refresh(stale) is True


def test_explicit_bilingual_off_is_fresh_for_non_students() -> None:
    """An explicit false is a real preference, not a missing column."""
    fresh = {
        "id": "7",
        "role": "teacher",
        "bilingual_ui_enabled": "0",
        "presenter_ui_locale": "",
    }
    assert user_cache_hash_needs_refresh(fresh) is False


def test_student_hash_still_refreshes_when_learning_fields_are_missing() -> None:
    """Student hashes still refresh when Learning Space fields were never written."""
    stale_student = {
        "id": "8",
        "role": "student",
        "bilingual_ui_enabled": "1",
        "presenter_ui_locale": "en",
    }
    assert user_cache_hash_needs_refresh(stale_student) is True
