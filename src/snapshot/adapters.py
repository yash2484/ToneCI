# src/snapshot/adapters.py
from __future__ import annotations
import time
from typing import Protocol
from pydantic import BaseModel
from snapshot.models import CaseConfig


class TTSResult(BaseModel):
    audio: bytes
    latency_ms: int
    voice_id: str
    model_id: str
    output_format: str


class STTResult(BaseModel):
    transcript: str


class AdapterProtocol(Protocol):
    def generate_speech(self, case: CaseConfig) -> TTSResult: ...
    def transcribe(self, audio: bytes, language_code: str | None = None) -> STTResult: ...


class ElevenLabsAdapter:
    def __init__(self, api_key: str) -> None:
        from elevenlabs.client import ElevenLabs
        self._client = ElevenLabs(api_key=api_key)

    def generate_speech(self, case: CaseConfig) -> TTSResult:
        start = time.monotonic()
        chunks = self._client.text_to_speech.convert(
            text=case.source_text,
            voice_id=case.voice_id,
            model_id=case.model_id,
            output_format=case.output_format,
        )
        # SDK may return a generator or bytes; normalise to bytes
        if isinstance(chunks, bytes):
            audio = chunks
        else:
            audio = b"".join(chunks)
        latency_ms = int((time.monotonic() - start) * 1000)
        return TTSResult(
            audio=audio,
            latency_ms=latency_ms,
            voice_id=case.voice_id,
            model_id=case.model_id,
            output_format=case.output_format,
        )

    def transcribe(self, audio: bytes, language_code: str | None = None) -> STTResult:
        import io
        kwargs: dict = dict(
            file=("audio.mp3", io.BytesIO(audio), "audio/mpeg"),
            model_id="scribe_v2",
        )
        if language_code is not None:
            kwargs["language_code"] = language_code
        result = self._client.speech_to_text.convert(**kwargs)
        return STTResult(transcript=result.text or "")


class FakeAdapter:
    """Deterministic adapter for unit tests — no network calls."""

    def __init__(self, speech_bytes: bytes, transcript: str) -> None:
        self._bytes = speech_bytes
        self._transcript = transcript

    def generate_speech(self, case: CaseConfig) -> TTSResult:
        return TTSResult(
            audio=self._bytes,
            latency_ms=0,
            voice_id=case.voice_id,
            model_id=case.model_id,
            output_format=case.output_format,
        )

    def transcribe(self, audio: bytes, language_code: str | None = None) -> STTResult:
        return STTResult(transcript=self._transcript)
