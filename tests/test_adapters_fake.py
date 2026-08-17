from snapshot.adapters import FakeAdapter, TTSResult, STTResult
from snapshot.models import CaseConfig, Tolerances


def _case() -> CaseConfig:
    return CaseConfig(
        id="t1",
        source_text="Hello.",
        expected_transcript="Hello.",
        required_phrases=[],
        voice_id="v1",
        model_id="m1",
        output_format="mp3_44100_128",
        tolerances=Tolerances(
            transcript_wer_threshold=0.15,
            duration_pct=0.10,
            duration_abs_ms=200,
            leading_silence_ms=150,
            trailing_silence_ms=150,
        ),
    )


def test_fake_generate_returns_fixed_bytes():
    adapter = FakeAdapter(speech_bytes=b"FAKEAUDIO", transcript="Hello.")
    result = adapter.generate_speech(_case())
    assert isinstance(result, TTSResult)
    assert result.audio == b"FAKEAUDIO"
    assert result.latency_ms >= 0


def test_fake_transcribe_returns_fixed_transcript():
    adapter = FakeAdapter(speech_bytes=b"FAKEAUDIO", transcript="Hello.")
    result = adapter.transcribe(b"FAKEAUDIO", language_code=None)
    assert isinstance(result, STTResult)
    assert result.transcript == "Hello."
