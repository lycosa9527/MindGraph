"""Header avatar rows for people in a MindMate seminar."""

from services.features.mindmate_collab.participant_faces import participant_face_payload


def test_face_uses_the_stored_name_and_emoji() -> None:
    """A joined teacher keeps the name and avatar already on their account."""
    face = participant_face_payload(7, "  Ada  ", " 🐱 ")
    assert face == {"user_id": 7, "name": "Ada", "avatar": "🐱"}


def test_blank_name_and_avatar_fall_back() -> None:
    """Missing profile fields still produce a usable circle."""
    face = participant_face_payload(4, "   ", None)
    assert face["name"] == "User 4"
    assert face["avatar"] is None
