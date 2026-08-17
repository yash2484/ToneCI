# src/snapshot/commands/approve.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from snapshot.models import ApprovalRecord, BaselineManifest, RunState, audio_hash
from snapshot.store import ArtifactStore


def approve_cases(
    run_id: str,
    case_ids: list[str],
    snapshots_dir: Path,
    runs_dir: Path,
) -> list[str]:
    """Promote named candidates to baselines with a full audit trail.

    Raises ValueError for ERROR-state candidates or unknown case IDs.
    Returns the list of approved case IDs.
    """
    store = ArtifactStore(snapshots_dir=snapshots_dir, runs_dir=runs_dir)
    run_result = store.read_run_results(run_id)

    # index run results by case id
    by_id = {c.case_id: c for c in run_result.cases}

    approved: list[str] = []
    for case_id in case_ids:
        if case_id not in by_id:
            raise ValueError(
                f"Case {case_id!r} not found in run {run_id!r}."
            )
        cr = by_id[case_id]
        if cr.state == RunState.ERROR:
            raise ValueError(
                f"Cannot approve case {case_id!r}: it has state ERROR. "
                "Fix the error and re-run `snapshot check` before approving."
            )

        candidate_audio = store.read_candidate(run_id, case_id)
        old_manifest = store.read_baseline_manifest(case_id)

        new_hash = audio_hash(candidate_audio)
        approval_record = ApprovalRecord(
            approved_at=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            previous_hash=old_manifest.audio_hash,
            new_hash=new_hash,
        )
        new_manifest = old_manifest.model_copy(update=dict(
            audio_hash=new_hash,
            size_bytes=len(candidate_audio),
            baseline_transcript=cr.candidate_transcript or old_manifest.baseline_transcript,
            approval_history=old_manifest.approval_history + [approval_record],
        ))

        store.promote_candidate_to_baseline(run_id, case_id, new_manifest)
        print(f"[approve] {case_id}: promoted candidate from run {run_id}")
        approved.append(case_id)

    return approved
