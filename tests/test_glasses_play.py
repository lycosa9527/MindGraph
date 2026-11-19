"""Slide-play codes and the one-slot queue the open course builder drains."""

import json

from services.learning_space.glasses_play import (
    PLAY_CONTINUE,
    TTL_SECONDS,
    _cue_for_cursor,
    cursor_is_finished,
    encode_recording,
    glasses_voice_path,
    next_follow_seq,
    play_target_user,
    play_cue,
    play_key,
    queue_voice_cue,
    read_follow,
    store_play,
    take_play,
    take_voice_cue,
    write_follow,
)

COURSE = "11111111-1111-4111-8111-111111111111"


class _FakeRedis:
    """The get/set/delete the play slot uses."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store one cue and remember its TTL."""
        self.values[key] = value
        if ex is not None:
            self.ttl[key] = ex

    def get(self, key: str) -> str | None:
        """Return the stored cue."""
        return self.values.get(key)

    def delete(self, key: str) -> None:
        """Drop the cue."""
        self.values.pop(key, None)


def test_a_tap_on_the_last_slide_is_the_end() -> None:
    """The last mark of the last slide has nowhere to go. An earlier mark still moves."""
    steps = [
        {"mark_step": 1, "mark_steps": 2, "glasses_line": "here"},
        {"mark_step": 1, "mark_steps": 1, "glasses_line": "there"},
    ]
    assert cursor_is_finished(steps, 0, 1, 0) is False
    assert cursor_is_finished(steps, 1, 1, 0) is True


def test_play_cue_falls_back_when_the_slide_has_no_line() -> None:
    """An empty line still gives the glasses something to say."""
    cue = play_cue({}, COURSE, 0)
    assert cue["display"] == PLAY_CONTINUE
    assert cue["reveal"] == ""
    spoken = play_cue({"glasses_line": "Welcome", "glasses_reveal": "clockwise"}, COURSE, 1)
    assert spoken["display"] == "Welcome"
    assert spoken["reveal"] == "clockwise"
    assert play_cue({"glasses_reveal": "spin"}, COURSE, 0)["reveal"] == ""
    voiced = play_cue({"glasses_line": "Welcome", "voice_url": glasses_voice_path(COURSE, 1)}, COURSE, 1)
    assert voiced["voice"] == glasses_voice_path(COURSE, 1)
    assert "voice" not in play_cue({"voice_url": "https://example.com/a.mp3"}, COURSE, 0)


def test_a_same_slide_tap_does_not_replay_the_recording() -> None:
    """The recording belongs to the slide. A later mark on that slide only says to continue."""
    steps = [{"glasses_line": "Welcome", "voice_url": glasses_voice_path(COURSE, 0)}]
    cue = _cue_for_cursor(
        steps,
        COURSE,
        {"index": 0, "mark": 2, "read": 0},
        action="next",
        slide_changed=False,
    )
    assert cue["display"] == PLAY_CONTINUE
    assert "voice" not in cue


def test_a_live_course_tap_reaches_the_instructor() -> None:
    """Every bound pair follows one course, and a tap asks the instructor to advance."""
    assert play_target_user({"instructor_id": 9}, 4) == 9
    assert play_target_user({"course_id": COURSE}, 4) == 4
    assert play_target_user(None, 4) == 4


def test_the_computer_slide_replaces_what_the_glasses_are_showing() -> None:
    """A newer slide is kept. The glasses ignore a sequence they already showed."""
    redis = _FakeRedis()
    assert next_follow_seq(redis, 4) == 1
    assert write_follow(redis, 4, {"seq": 1, "active": True, "display": "one"}) is True
    assert next_follow_seq(redis, 4) == 2
    assert write_follow(redis, 4, {"seq": 2, "active": True, "display": "two"}) is True
    follow = read_follow(redis, 4)
    assert follow is not None
    assert follow["display"] == "two"
    assert follow["seq"] == 2


def test_a_glasses_recording_is_queued_for_the_bound_pair() -> None:
    """The editor asks the glasses to play the file it just created, once."""
    redis = _FakeRedis()
    assert encode_recording(b"mp3") == "bXAz"
    assert queue_voice_cue(redis, 4, COURSE, 1) is True
    assert take_voice_cue(redis, 4) == (COURSE, 1)
    assert take_voice_cue(redis, 4) is None


def test_queue_keeps_the_newest_cue_and_clears_on_drain() -> None:
    """A second scan replaces the first. The builder reads it once."""
    redis = _FakeRedis()
    first = play_cue({"glasses_line": "one"}, COURSE, 0)
    second = play_cue({"glasses_line": "two", "glasses_reveal": "highlight"}, COURSE, 1)
    assert store_play(redis, 4, first) is True
    assert store_play(redis, 4, second) is True
    assert take_play(redis, 4) == second
    assert take_play(redis, 4) is None
    assert redis.ttl[play_key(4)] == TTL_SECONDS


def test_bytes_from_redis_are_decoded() -> None:
    """A client without decode_responses still yields the cue."""

    class _BytesRedis(_FakeRedis):
        """Returns the raw bytes a Redis client emits without decode_responses."""

        def get(self, key: str) -> bytes | None:
            """Encode the stored cue the way Redis would."""
            raw = self.values.get(key)
            if raw is None:
                return None
            return raw.encode("utf-8")

    redis = _BytesRedis()
    cue = play_cue({"glasses_line": "Welcome"}, COURSE, 0)
    store_play(redis, 9, cue)
    assert take_play(redis, 9) == json.loads(json.dumps(cue))
