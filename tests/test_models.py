# tests/test_models.py
import pytest
from pathlib import Path
from snapshot.models import (
    Tolerances, CaseConfig, SnapshotSuite, RunState,
    CheckReason, CaseResult, RunResult, load_suite,
)

def test_runstate_values():
    assert RunState.PASS.value == "PASS"
    assert RunState.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
    assert RunState.ERROR.value == "ERROR"
    assert len(RunState) == 3

def test_tolerances_defaults():
    t = Tolerances(
        transcript_wer_threshold=0.15,
        duration_pct=0.10,
        duration_abs_ms=200,
        leading_silence_ms=150,
        trailing_silence_ms=150,
    )
    assert t.duration_pct == 0.10

def test_case_config_roundtrip():
    cc = CaseConfig(
        id="x",
        source_text="Hello.",
        expected_transcript="Hello.",
        required_phrases=["Hello"],
        voice_id="v1",
        model_id="m1",
        output_format="mp3_44100_128",
        tolerances=Tolerances(0.15, 0.10, 200, 150, 150),
    )
    assert cc.id == "x"

def test_load_suite_valid(tmp_path):
    yaml_content = """
cases:
  - id: demo
    source_text: "Hi."
    expected_transcript: "Hi."
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
"""
    p = tmp_path / "snapshots.yaml"
    p.write_text(yaml_content)
    suite = load_suite(p)
    assert len(suite.cases) == 1
    assert suite.cases[0].id == "demo"

def test_load_suite_missing_file():
    with pytest.raises(FileNotFoundError):
        load_suite(Path("nonexistent.yaml"))

def test_duplicate_case_ids_rejected(tmp_path):
    yaml_content = """
cases:
  - id: dup
    source_text: "A."
    expected_transcript: "A."
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
  - id: dup
    source_text: "B."
    expected_transcript: "B."
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
"""
    p = tmp_path / "snapshots.yaml"
    p.write_text(yaml_content)
    with pytest.raises(ValueError, match="Duplicate case id"):
        load_suite(p)
