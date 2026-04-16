"""Tests for services/mindbot/dify/usage_parse.py."""

from __future__ import annotations

from services.mindbot.dify.usage_parse import (
    parse_dify_usage_from_blocking_response,
    parse_dify_usage_from_stream_event,
)


class TestParseFromStreamEvent:
    """Tests for parse_dify_usage_from_stream_event."""

    def test_happy_path_numeric_tokens(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

    def test_string_token_counts_are_coerced(self) -> None:
        """Regression test for F2: string token values must not silently become 0."""
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": "15",
                    "completion_tokens": "25",
                    "total_tokens": "40",
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result == {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}

    def test_invalid_string_token_counts_become_zero(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": "not-a-number",
                    "completion_tokens": 5,
                    "total_tokens": 5,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result is not None
        assert result["prompt_tokens"] == 0

    def test_missing_token_fields_returns_none(self) -> None:
        ev = {"metadata": {"usage": {}}}
        result = parse_dify_usage_from_stream_event(ev)
        assert result is None

    def test_null_token_fields_returns_none(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result is None

    def test_missing_metadata_returns_none(self) -> None:
        ev = {"event": "message_end"}
        result = parse_dify_usage_from_stream_event(ev)
        assert result is None

    def test_missing_usage_in_metadata_returns_none(self) -> None:
        ev = {"metadata": {}}
        result = parse_dify_usage_from_stream_event(ev)
        assert result is None

    def test_non_dict_metadata_returns_none(self) -> None:
        ev = {"metadata": "bad"}
        result = parse_dify_usage_from_stream_event(ev)
        assert result is None

    def test_float_token_counts_are_truncated(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": 7.9,
                    "completion_tokens": 3.1,
                    "total_tokens": 11.0,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 11}

    def test_total_inferred_from_prompt_and_completion(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 0,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result is not None
        assert result["total_tokens"] == 30

    def test_bool_token_counts_treated_as_zero(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": True,
                    "completion_tokens": 5,
                    "total_tokens": 5,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result is not None
        assert result["prompt_tokens"] == 0

    def test_negative_token_counts_clamped_to_zero(self) -> None:
        ev = {
            "metadata": {
                "usage": {
                    "prompt_tokens": -5,
                    "completion_tokens": 10,
                    "total_tokens": 10,
                }
            }
        }
        result = parse_dify_usage_from_stream_event(ev)
        assert result is not None
        assert result["prompt_tokens"] == 0


class TestParseFromBlockingResponse:
    """Tests for parse_dify_usage_from_blocking_response."""

    def test_happy_path_blocking_response(self) -> None:
        resp = {
            "metadata": {
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 15,
                    "total_tokens": 20,
                }
            }
        }
        result = parse_dify_usage_from_blocking_response(resp)
        assert result == {"prompt_tokens": 5, "completion_tokens": 15, "total_tokens": 20}

    def test_string_tokens_in_blocking_response(self) -> None:
        """Regression: string tokens in blocking path must also be coerced."""
        resp = {
            "metadata": {
                "usage": {
                    "prompt_tokens": "8",
                    "completion_tokens": "12",
                    "total_tokens": "20",
                }
            }
        }
        result = parse_dify_usage_from_blocking_response(resp)
        assert result == {"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20}

    def test_missing_metadata_returns_none(self) -> None:
        result = parse_dify_usage_from_blocking_response({})
        assert result is None

    def test_all_zero_returns_none(self) -> None:
        resp = {
            "metadata": {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            }
        }
        result = parse_dify_usage_from_blocking_response(resp)
        assert result is None
