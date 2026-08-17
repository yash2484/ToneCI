# tests/test_record.py
import struct, wave, math
from pathlib import Path
from unittest.mock import patch
import pytest
from snapshot.commands.record import record_suite
from snapshot.adapters import FakeAdapter
from snapshot.audio import AudioMeasurements
from snapshot.store import ArtifactStore


_FAKE_MEASUREMENTS = AudioMeasurements(
    duration_ms=300,
    leading_silence_ms=0,
    trailing_silence_ms=0,
    size_bytes=1024,
    audio_hash="a" * 64,
)


def _make_wav(duration_ms: int = 300) -> bytes:
    """Return minimal 44100 Hz mono 16-bit WAV bytes."""
    sample_rate = 44100
    n = int(sample_rate * duration_ms / 1000)
    frames = b"".join(
        struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(n)
    )
    import io
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return buf.getvalue()


def _write_suite(tmp_path: Path, case_id: str = "c1") -> Path:
    p = tmp_path / "snapshots.yaml"
    p.write_text(f"""
cases:
  - id: {case_id}
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


@patch("snapshot.commands.record.measure_audio", return_value=_FAKE_MEASUREMENTS)
def test_record_creates_baseline(mock_measure, tmp_path):
    suite_path = _write_suite(tmp_path)
    audio = _make_wav()
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello.")
    recorded = record_suite(
        suite_path=suite_path,
        snapshots_dir=tmp_path / "snapshots",
        runs_dir=tmp_path / "runs",
        adapter=adapter,
    )
    assert "c1" in recorded
    assert (tmp_path / "snapshots" / "c1" / "baseline.mp3").exists()
    assert (tmp_path / "snapshots" / "c1" / "manifest.json").exists()
    mock_measure.assert_called_once()


@patch("snapshot.commands.record.measure_audio", return_value=_FAKE_MEASUREMENTS)
def test_record_skips_existing_baseline(mock_measure, tmp_path):
    suite_path = _write_suite(tmp_path)
    audio = _make_wav()
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello.")
    # record once
    record_suite(suite_path, tmp_path / "snapshots", tmp_path / "runs", adapter)
    # record again — should skip without raising
    recorded = record_suite(suite_path, tmp_path / "snapshots", tmp_path / "runs", adapter)
    assert recorded == []
    # measure_audio called only once (second pass skips)
    assert mock_measure.call_count == 1
