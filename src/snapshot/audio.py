# src/snapshot/audio.py
from __future__ import annotations
import hashlib
from io import BytesIO
from pathlib import Path
from pydantic import BaseModel
from pydub import AudioSegment
from pydub.silence import detect_leading_silence


# Documented constants — changing either alters silence measurements.
SILENCE_AMPLITUDE_THRESHOLD: float = -50.0   # dBFS
SILENCE_MIN_WINDOW_MS: int = 50              # minimum chunk size for detection


class AudioMeasurements(BaseModel):
    duration_ms: int
    leading_silence_ms: int
    trailing_silence_ms: int
    size_bytes: int
    audio_hash: str


def _leading_silence_ms(seg: AudioSegment) -> int:
    return detect_leading_silence(seg, silence_threshold=SILENCE_AMPLITUDE_THRESHOLD,
                                  chunk_size=SILENCE_MIN_WINDOW_MS)


def _trailing_silence_ms(seg: AudioSegment) -> int:
    return detect_leading_silence(seg.reverse(),
                                  silence_threshold=SILENCE_AMPLITUDE_THRESHOLD,
                                  chunk_size=SILENCE_MIN_WINDOW_MS)


def measure_audio(path: Path) -> AudioMeasurements:
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    data = path.read_bytes()
    return _measure_audio(data, str(path))


def measure_audio_bytes(data: bytes, format: str) -> AudioMeasurements:
    return _measure_audio(data, BytesIO(data), format)


def _measure_audio(
    data: bytes, source: str | BytesIO, format: str | None = None
) -> AudioMeasurements:
    seg = AudioSegment.from_file(source, format=format)
    return AudioMeasurements(
        duration_ms=int(len(seg)),
        leading_silence_ms=_leading_silence_ms(seg),
        trailing_silence_ms=_trailing_silence_ms(seg),
        size_bytes=len(data),
        audio_hash=hashlib.sha256(data).hexdigest(),
    )
