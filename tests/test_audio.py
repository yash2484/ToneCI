# tests/test_audio.py
import struct, wave
from io import BytesIO
from pathlib import Path
import pytest
from snapshot.audio import measure_audio, measure_audio_bytes, AudioMeasurements, SILENCE_AMPLITUDE_THRESHOLD


def _write_wav(path: Path, duration_ms: int, amplitude: float = 0.8) -> None:
    """Write a minimal mono 16-bit 44100 Hz WAV file."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    import math
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = b""
        for i in range(num_samples):
            val = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames += struct.pack("<h", val)
        wf.writeframes(frames)


def _write_silent_wav(path: Path, duration_ms: int) -> None:
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)


def test_measure_tone_returns_measurements(tmp_path):
    p = tmp_path / "tone.wav"
    _write_wav(p, duration_ms=500)
    m = measure_audio(p)
    assert isinstance(m, AudioMeasurements)
    assert m.duration_ms >= 450
    assert m.size_bytes > 0
    assert len(m.audio_hash) == 64  # sha256 hex


def test_measure_silent_clip(tmp_path):
    p = tmp_path / "silent.wav"
    _write_silent_wav(p, duration_ms=300)
    m = measure_audio(p)
    assert m.duration_ms >= 250
    # fully silent — leading and trailing silence should cover most of the clip
    assert m.leading_silence_ms + m.trailing_silence_ms >= m.duration_ms * 0.8


def test_measure_missing_file():
    with pytest.raises(FileNotFoundError):
        measure_audio(Path("nonexistent.mp3"))


def test_hash_is_deterministic(tmp_path):
    p = tmp_path / "tone.wav"
    _write_wav(p, duration_ms=200)
    m1 = measure_audio(p)
    m2 = measure_audio(p)
    assert m1.audio_hash == m2.audio_hash


def test_measure_audio_bytes_returns_measurements():
    buffer = BytesIO()
    with wave.open(buffer, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * 4410)

    measurements = measure_audio_bytes(buffer.getvalue(), "wav")

    assert measurements.duration_ms >= 100
    assert measurements.size_bytes > 0
    assert len(measurements.audio_hash) == 64
