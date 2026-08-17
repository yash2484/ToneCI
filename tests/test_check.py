# tests/test_check.py
import struct, wave, math, io
from pathlib import Path
from unittest.mock import patch
import pytest
from snapshot.commands.record import record_suite
from snapshot.commands.check import check_suite
from snapshot.adapters import FakeAdapter
from snapshot.audio import AudioMeasurements
from snapshot.models import RunState

_FAKE_MEASUREMENTS = AudioMeasurements(
    duration_ms=300,
    leading_silence_ms=0,
    trailing_silence_ms=0,
    size_bytes=1024,
    audio_hash="a" * 64,
)


def _wav(duration_ms: int = 400, freq: int = 440, amp: float = 0.5) -> bytes:
    sr = 44100
    n = int(sr * duration_ms / 1000)
    frames = b"".join(
        struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr)))
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
    source_text: "Hello world."
    expected_transcript: "Hello world."
    required_phrases:
      - "Hello world"
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


def _dirs(tmp_path: Path):
    return tmp_path / "snapshots", tmp_path / "runs"


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
def test_check_pass(mock_check_m, mock_record_m, tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, adapter)
    result = check_suite(suite, snap, runs, adapter)
    assert result.state == RunState.PASS
    assert all(c.state == RunState.PASS for c in result.cases)


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
def test_check_review_required_on_missing_phrase(mock_check_m, mock_record_m, tmp_path):
    audio = _wav(400)
    # baseline has "Hello world.", candidate transcript missing required phrase
    base_adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, base_adapter)

    # now check with a candidate that drops the required phrase
    cand_adapter = FakeAdapter(speech_bytes=audio, transcript="Goodbye earth.")
    result = check_suite(suite, snap, runs, cand_adapter)
    assert result.state == RunState.REVIEW_REQUIRED


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
def test_check_does_not_mutate_baseline(mock_check_m, mock_record_m, tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, adapter)
    original = (snap / "c1" / "baseline.mp3").read_bytes()
    check_suite(suite, snap, runs, adapter)
    assert (snap / "c1" / "baseline.mp3").read_bytes() == original


@patch("snapshot.commands.record.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
@patch("snapshot.commands.check.measure_audio_bytes", return_value=_FAKE_MEASUREMENTS)
def test_check_error_when_no_baseline(mock_check_m, mock_record_m, tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    # intentionally skip record step
    result = check_suite(suite, snap, runs, adapter)
    assert result.state == RunState.ERROR
