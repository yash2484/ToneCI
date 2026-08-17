# src/snapshot/commands/check.py
from __future__ import annotations
import tempfile
from pathlib import Path
from snapshot.adapters import AdapterProtocol
from snapshot.audio import measure_audio
from snapshot.comparison import (
    aggregate_state,
    check_duration_drift,
    check_required_phrases,
    check_silence_drift,
    check_transcript_fidelity,
)
from snapshot.models import (
    CaseResult, RunResult, RunState, CheckReason, audio_hash, load_suite
)
from snapshot.store import ArtifactStore


def _check_case(case, store: ArtifactStore, adapter: AdapterProtocol) -> CaseResult:
    if not store.baseline_exists(case.id):
        return CaseResult(
            case_id=case.id,
            state=RunState.ERROR,
            reasons=[CheckReason(check="missing_baseline",
                                 detail=f"No baseline found for {case.id!r}. Run `snapshot record` first.")],
        )
    try:
        manifest = store.read_baseline_manifest(case.id)
        tts = adapter.generate_speech(case)

        # write candidate to a temp dir for measurement; TemporaryDirectory
        # avoids PermissionError on Windows (pydub holds the file open)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / f"{case.id}.mp3"
            tmp_path.write_bytes(tts.audio)
            cand_m = measure_audio(tmp_path)

        stt = adapter.transcribe(tts.audio)

        tol = case.tolerances
        reasons = (
            check_transcript_fidelity(case.expected_transcript, stt.transcript,
                                      tol.transcript_wer_threshold)
            + check_required_phrases(case.required_phrases, stt.transcript)
            + check_duration_drift(manifest.duration_ms, cand_m.duration_ms,
                                   tol.duration_pct, tol.duration_abs_ms)
            + check_silence_drift(
                manifest.leading_silence_ms, cand_m.leading_silence_ms,
                manifest.trailing_silence_ms, cand_m.trailing_silence_ms,
                tol.leading_silence_ms, tol.trailing_silence_ms,
            )
        )

        return CaseResult(
            case_id=case.id,
            state=aggregate_state(reasons, error=False),
            reasons=reasons,
            baseline_transcript=manifest.baseline_transcript,
            candidate_transcript=stt.transcript,
            baseline_duration_ms=manifest.duration_ms,
            candidate_duration_ms=cand_m.duration_ms,
            baseline_leading_silence_ms=manifest.leading_silence_ms,
            candidate_leading_silence_ms=cand_m.leading_silence_ms,
            baseline_trailing_silence_ms=manifest.trailing_silence_ms,
            candidate_trailing_silence_ms=cand_m.trailing_silence_ms,
            generation_latency_ms=tts.latency_ms,
            baseline_size_bytes=manifest.size_bytes,
            candidate_size_bytes=cand_m.size_bytes,
            baseline_hash=manifest.audio_hash,
            candidate_hash=audio_hash(tts.audio),
        )
    except Exception as exc:
        return CaseResult(
            case_id=case.id,
            state=RunState.ERROR,
            reasons=[CheckReason(check="exception", detail=str(exc))],
        )


def check_suite(
    suite_path: Path,
    snapshots_dir: Path,
    runs_dir: Path,
    adapter: AdapterProtocol,
) -> RunResult:
    suite = load_suite(suite_path)
    store = ArtifactStore(snapshots_dir=snapshots_dir, runs_dir=runs_dir)
    run_id = store.new_run_id()

    case_results: list[CaseResult] = []
    for case in suite.cases:
        print(f"[check] {case.id}: generating candidate...")
        cr = _check_case(case, store, adapter)
        # write candidate audio if generation succeeded (second call, per brief)
        if cr.candidate_hash is not None:
            try:
                tts = adapter.generate_speech(case)
                store.write_candidate(run_id, case.id, tts.audio)
            except Exception:
                pass  # candidate audio unavailable; result still valid
        case_results.append(cr)
        print(f"[check] {case.id}: {cr.state.value}")

    # aggregate run state: ERROR > REVIEW_REQUIRED > PASS
    if any(c.state == RunState.ERROR for c in case_results):
        run_state = RunState.ERROR
    elif any(c.state == RunState.REVIEW_REQUIRED for c in case_results):
        run_state = RunState.REVIEW_REQUIRED
    else:
        run_state = RunState.PASS

    result = RunResult(run_id=run_id, state=run_state, cases=case_results)
    store.write_run_results(run_id, result)
    return result
