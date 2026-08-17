# tests/test_comparison.py
import pytest
from snapshot.comparison import (
    normalize_transcript,
    word_error_rate,
    check_transcript_fidelity,
    check_required_phrases,
    check_duration_drift,
    check_silence_drift,
    aggregate_state,
)
from snapshot.models import RunState


def test_normalize_strips_punctuation():
    assert normalize_transcript("Hello, World!") == "hello world"


def test_normalize_collapses_whitespace():
    assert normalize_transcript("  hello   world  ") == "hello world"


def test_wer_identical():
    assert word_error_rate("hello world", "hello world") == 0.0


def test_wer_one_substitution():
    # reference: "hello world" (2 words), hypothesis replaces 1
    rate = word_error_rate("hello world", "hello earth")
    assert abs(rate - 0.5) < 0.01


def test_wer_all_wrong():
    rate = word_error_rate("hello world", "foo bar")
    assert rate == 1.0


def test_fidelity_pass():
    reasons = check_transcript_fidelity("hello world", "hello world", threshold=0.15)
    assert reasons == []


def test_fidelity_review_required():
    reasons = check_transcript_fidelity("hello world test", "goodbye world test", threshold=0.15)
    assert any(r.check == "transcript_fidelity" for r in reasons)


def test_required_phrases_all_present():
    reasons = check_required_phrases(["hello", "world"], "hello world test")
    assert reasons == []


def test_required_phrases_missing():
    reasons = check_required_phrases(["missing_phrase"], "hello world")
    assert any(r.check == "required_phrase" for r in reasons)
    assert "missing_phrase" in reasons[0].detail


def test_required_phrases_empty_list():
    assert check_required_phrases([], "anything") == []


def test_duration_drift_within_pct():
    # baseline 1000ms, candidate 1050ms, 10% tolerance = 100ms allowed
    reasons = check_duration_drift(1000, 1050, pct=0.10, abs_floor_ms=200)
    assert reasons == []


def test_duration_drift_within_abs_floor():
    # baseline 100ms, candidate 115ms; 10% of 100 = 10ms < floor 200ms, floor wins
    reasons = check_duration_drift(100, 115, pct=0.10, abs_floor_ms=200)
    assert reasons == []


def test_duration_drift_exceeds_both():
    # baseline 1000ms, candidate 1500ms, 10% = 100ms, floor 200ms — both exceeded
    reasons = check_duration_drift(1000, 1500, pct=0.10, abs_floor_ms=200)
    assert any(r.check == "duration_drift" for r in reasons)


def test_silence_drift_within_tolerance():
    reasons = check_silence_drift(100, 120, 100, 110, leading_tol_ms=150, trailing_tol_ms=150)
    assert reasons == []


def test_leading_silence_exceeds():
    reasons = check_silence_drift(100, 400, 100, 100, leading_tol_ms=150, trailing_tol_ms=150)
    assert any(r.check == "leading_silence_drift" for r in reasons)


def test_trailing_silence_exceeds():
    reasons = check_silence_drift(100, 100, 100, 400, leading_tol_ms=150, trailing_tol_ms=150)
    assert any(r.check == "trailing_silence_drift" for r in reasons)


def test_aggregate_pass():
    assert aggregate_state([], error=False) == RunState.PASS


def test_aggregate_review():
    from snapshot.models import CheckReason
    r = CheckReason(check="duration_drift", detail="delta 500ms")
    assert aggregate_state([r], error=False) == RunState.REVIEW_REQUIRED


def test_aggregate_error_dominates():
    from snapshot.models import CheckReason
    r = CheckReason(check="duration_drift", detail="delta 500ms")
    assert aggregate_state([r], error=True) == RunState.ERROR


def test_aggregate_error_no_reasons():
    assert aggregate_state([], error=True) == RunState.ERROR
