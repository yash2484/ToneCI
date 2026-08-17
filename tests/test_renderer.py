# tests/test_renderer.py
from snapshot.renderer import render_report
from snapshot.models import RunResult, CaseResult, RunState, CheckReason


def _result(state: RunState = RunState.PASS) -> RunResult:
    return RunResult(
        run_id="20260817T000000Z-abc123",
        state=state,
        cases=[
            CaseResult(
                case_id="c1",
                state=state,
                reasons=[CheckReason(check="duration_drift", detail="delta 500ms")]
                        if state == RunState.REVIEW_REQUIRED else [],
                baseline_transcript="Hello world.",
                candidate_transcript="Hello world.",
                baseline_duration_ms=500,
                candidate_duration_ms=1000,
                baseline_leading_silence_ms=50,
                candidate_leading_silence_ms=50,
                baseline_trailing_silence_ms=50,
                candidate_trailing_silence_ms=50,
                generation_latency_ms=320,
                baseline_size_bytes=1024,
                candidate_size_bytes=2048,
                baseline_hash="aaa",
                candidate_hash="bbb",
            )
        ],
    )


def test_render_returns_html_string():
    html = render_report(_result(), baseline_audio={"c1": b"FAKE"}, candidate_audio={"c1": b"FAKE"})
    assert isinstance(html, str)
    assert "<html" in html.lower()


def test_render_contains_run_state():
    html = render_report(_result(RunState.PASS), {}, {})
    assert "PASS" in html


def test_render_review_contains_reasons():
    html = render_report(
        _result(RunState.REVIEW_REQUIRED),
        baseline_audio={"c1": b"FAKE"},
        candidate_audio={"c1": b"FAKE"},
    )
    assert "duration_drift" in html
    assert "REVIEW_REQUIRED" in html


def test_render_embeds_audio_as_base64():
    html = render_report(
        _result(),
        baseline_audio={"c1": b"AUDIO"},
        candidate_audio={"c1": b"AUDIO"},
    )
    assert "data:audio" in html


def test_render_shows_both_transcripts():
    html = render_report(
        _result(),
        baseline_audio={"c1": b"AUDIO"},
        candidate_audio={"c1": b"AUDIO"},
    )
    assert "Hello world." in html


def test_only_three_state_labels_appear():
    html = render_report(_result(RunState.REVIEW_REQUIRED), {}, {})
    for forbidden in ["FAIL", "WARN", "WARNING"]:
        assert forbidden not in html
