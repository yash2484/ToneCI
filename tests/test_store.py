# tests/test_store.py
import pytest
from pathlib import Path
from snapshot.store import ArtifactStore
from snapshot.models import (
    BaselineManifest, RunResult, RunState, CaseResult, ApprovalRecord
)


def _store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(
        snapshots_dir=tmp_path / "snapshots",
        runs_dir=tmp_path / "runs",
    )


def _manifest(case_id: str = "c1") -> BaselineManifest:
    return BaselineManifest(
        case_id=case_id,
        created_at="2026-08-17T00:00:00",
        voice_id="v1", model_id="m1", output_format="mp3_44100_128",
        source_text="Hello.", expected_transcript="Hello.",
        baseline_transcript="Hello.",
        duration_ms=500, leading_silence_ms=50, trailing_silence_ms=50,
        size_bytes=100, audio_hash="abc",
    )


def test_baseline_not_exists(tmp_path):
    s = _store(tmp_path)
    assert not s.baseline_exists("c1")


def test_write_and_read_baseline(tmp_path):
    s = _store(tmp_path)
    s.write_baseline("c1", b"AUDIO", _manifest("c1"))
    assert s.baseline_exists("c1")
    assert s.read_baseline_audio("c1") == b"AUDIO"
    m = s.read_baseline_manifest("c1")
    assert m.case_id == "c1"


def test_write_baseline_refuses_overwrite(tmp_path):
    s = _store(tmp_path)
    s.write_baseline("c1", b"AUDIO", _manifest("c1"))
    with pytest.raises(FileExistsError):
        s.write_baseline("c1", b"NEW", _manifest("c1"))


def test_write_and_read_candidate(tmp_path):
    s = _store(tmp_path)
    run_id = s.new_run_id()
    path = s.write_candidate(run_id, "c1", b"CANDIDATE")
    assert path.exists()
    assert s.read_candidate(run_id, "c1") == b"CANDIDATE"


def test_write_and_read_run_results(tmp_path):
    s = _store(tmp_path)
    run_id = s.new_run_id()
    result = RunResult(
        run_id=run_id,
        state=RunState.PASS,
        cases=[CaseResult(case_id="c1", state=RunState.PASS)],
    )
    s.write_run_results(run_id, result)
    loaded = s.read_run_results(run_id)
    assert loaded.state == RunState.PASS
    assert loaded.cases[0].case_id == "c1"


def test_promote_candidate_updates_baseline(tmp_path):
    s = _store(tmp_path)
    # seed original baseline
    s.write_baseline("c1", b"OLD", _manifest("c1"))
    # write a candidate in a run
    run_id = s.new_run_id()
    s.write_candidate(run_id, "c1", b"NEW")
    new_manifest = BaselineManifest(
        case_id="c1", created_at="2026-08-17T01:00:00",
        voice_id="v1", model_id="m1", output_format="mp3_44100_128",
        source_text="Hello.", expected_transcript="Hello.",
        baseline_transcript="Hello.",
        duration_ms=510, leading_silence_ms=50, trailing_silence_ms=50,
        size_bytes=110, audio_hash="def",
        approval_history=[
            ApprovalRecord(approved_at="2026-08-17T01:00:00",
                           run_id=run_id, previous_hash="abc", new_hash="def")
        ],
    )
    s.promote_candidate_to_baseline(run_id, "c1", new_manifest)
    assert s.read_baseline_audio("c1") == b"NEW"
    m = s.read_baseline_manifest("c1")
    assert len(m.approval_history) == 1
