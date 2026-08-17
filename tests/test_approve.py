# tests/test_approve.py
import struct, wave, math, io
from pathlib import Path
from unittest.mock import patch
import pytest
from snapshot.commands.record import record_suite
from snapshot.commands.check import check_suite
from snapshot.commands.approve import approve_cases
from snapshot.adapters import FakeAdapter
from snapshot.audio import AudioMeasurements
from snapshot.models import RunState

_FAKE_M = AudioMeasurements(
    duration_ms=300,
    leading_silence_ms=0,
    trailing_silence_ms=0,
    size_bytes=100,
    audio_hash="a" * 64,
)


def _wav(duration_ms: int = 300) -> bytes:
    sr, n = 44100, int(44100 * duration_ms / 1000)
    frames = b"".join(
        struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / sr)))
        for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(frames)
    return buf.getvalue()


def _suite(tmp_path: Path) -> Path:
    p = tmp_path / "snapshots.yaml"
    p.write_text("""
cases:
  - id: c1
    source_text: "Hello."
    expected_transcript: "Hello."
    required_phrases: []
    voice_id: v1
    model_id: m1
    output_format: mp3_44100_128
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 200
      leading_silence_ms: 150
      trailing_silence_ms: 150
""")
    return p


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_M)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_M)
def test_approve_promotes_candidate(mock_check_m, mock_record_m, tmp_path):
    audio_v1 = _wav(300)
    audio_v2 = _wav(350)
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)

    # baseline with v1
    record_suite(suite, snap, runs, FakeAdapter(audio_v1, "Hello."))
    original = (snap / "c1" / "baseline.mp3").read_bytes()

    # check with v2 — gets REVIEW_REQUIRED or PASS; either can be approved
    result = check_suite(suite, snap, runs, FakeAdapter(audio_v2, "Hello."))
    run_id = result.run_id

    approved = approve_cases(run_id, ["c1"], snap, runs)
    assert "c1" in approved
    assert (snap / "c1" / "baseline.mp3").read_bytes() != original

    # manifest should have one approval record
    from snapshot.store import ArtifactStore
    store = ArtifactStore(snap, runs)
    manifest = store.read_baseline_manifest("c1")
    assert len(manifest.approval_history) == 1
    assert manifest.approval_history[0].run_id == run_id


@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_M)
def test_approve_rejects_error_candidate(mock_check_m, tmp_path):
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)
    # skip record — check will ERROR (no baseline)
    result = check_suite(suite, snap, runs, FakeAdapter(_wav(), "Hello."))
    run_id = result.run_id
    with pytest.raises(ValueError, match="ERROR"):
        approve_cases(run_id, ["c1"], snap, runs)


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_M)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_M)
def test_approve_rejects_unknown_case(mock_check_m, mock_record_m, tmp_path):
    audio = _wav()
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)
    record_suite(suite, snap, runs, FakeAdapter(audio, "Hello."))
    result = check_suite(suite, snap, runs, FakeAdapter(audio, "Hello."))
    with pytest.raises(ValueError, match="not found"):
        approve_cases(result.run_id, ["nonexistent"], snap, runs)
