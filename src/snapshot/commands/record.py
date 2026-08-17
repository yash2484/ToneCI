# src/snapshot/commands/record.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from snapshot.adapters import AdapterProtocol
from snapshot.audio import measure_audio_bytes
from snapshot.models import BaselineManifest, audio_hash, load_suite
from snapshot.store import ArtifactStore


def record_suite(
    suite_path: Path,
    snapshots_dir: Path,
    runs_dir: Path,
    adapter: AdapterProtocol,
) -> list[str]:
    suite = load_suite(suite_path)
    store = ArtifactStore(snapshots_dir=snapshots_dir, runs_dir=runs_dir)
    recorded: list[str] = []

    for case in suite.cases:
        if store.baseline_exists(case.id):
            print(f"[skip] {case.id}: baseline already exists")
            continue

        print(f"[record] {case.id}: generating baseline...")
        tts = adapter.generate_speech(case)
        stt = adapter.transcribe(tts.audio)

        measurements = measure_audio_bytes(tts.audio, "mp3")

        manifest = BaselineManifest(
            case_id=case.id,
            created_at=datetime.now(timezone.utc).isoformat(),
            voice_id=case.voice_id,
            model_id=case.model_id,
            output_format=case.output_format,
            source_text=case.source_text,
            expected_transcript=case.expected_transcript,
            baseline_transcript=stt.transcript,
            duration_ms=measurements.duration_ms,
            leading_silence_ms=measurements.leading_silence_ms,
            trailing_silence_ms=measurements.trailing_silence_ms,
            size_bytes=measurements.size_bytes,
            audio_hash=audio_hash(tts.audio),
        )
        store.write_baseline(case.id, tts.audio, manifest)
        print(f"[record] {case.id}: baseline written (latency {tts.latency_ms}ms)")
        recorded.append(case.id)

    return recorded
