# TTS Snapshot CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI that catches review-worthy changes in ElevenLabs-rendered speech by comparing candidates against Git-tracked baselines and producing a side-by-side listening report.

**Architecture:** A Python CLI orchestrates focused modules: typed config/result models, a pure comparison engine, an audio analyzer, typed ElevenLabs adapters, an artifact store, and an HTML report renderer. The comparison engine has no SDK dependency so fakes can drive unit tests. Commands record baselines, check candidates, and approve named replacements.

**Tech Stack:** Python 3.11+, typer, pydantic v2, elevenlabs SDK, pydub (audio analysis), jinja2 (report), pytest, ruff.

**Spec:** design/001-product-and-architecture.md, design/002-snapshot-contract.md, PROJECT.md

## Global Constraints

- Python 3.11+ only. No walrus operator in contexts that confuse 3.10.
- Pydantic v2 models throughout. Use `model_validate`, not `parse_obj`.
- Three result states only: `PASS`, `REVIEW_REQUIRED`, `ERROR`. Never `FAIL` or `WARN`.
- `snapshot check` must never write to `snapshots/<case-id>/`. Read-only on baselines.
- `snapshot record` must refuse if `snapshots/<case-id>/baseline.mp3` already exists.
- `snapshot approve` requires explicit case IDs; no approve-all path.
- Validate the full YAML suite before any paid ElevenLabs API call.
- Secrets from environment variables only. Never log or embed them.
- Exit 0 = PASS, 1 = REVIEW_REQUIRED, 2 = ERROR.
- `runs/` and `runs/**` are git-ignored. `snapshots/` is git-tracked.
- Duration tolerance = `max(baseline_ms * pct, abs_floor_ms)`.
- Latency is metadata; it never affects state or exit code.
- Audio hashes are audit metadata; they never gate results.

---

## File Map

```
src/
  snapshot/
    __init__.py
    models.py          # CaseConfig, RunResult, CaseResult, BaselineManifest, ApprovalRecord
    comparison.py      # pure comparison functions, state aggregation
    audio.py           # AudioMeasurements, duration + silence analysis via pydub
    adapters.py        # ElevenLabsAdapter (TTS + STT), AdapterProtocol for fakes
    store.py           # ArtifactStore: baseline reads/writes, run directory management
    renderer.py        # HTML report via Jinja2, embedded base64 audio
    commands/
      __init__.py
      record.py        # `snapshot record` command logic
      check.py         # `snapshot check` command logic
      approve.py       # `snapshot approve` command logic
    cli.py             # typer app wiring all three commands
cases/
  snapshots.yaml       # test suite
snapshots/             # git-tracked baseline audio + manifests
runs/                  # git-ignored run artifacts
tests/
  fixtures/
    short_silence.mp3  # ~0.5 s synthetic clip for unit tests
    short_tone.mp3     # ~0.5 s 440 Hz tone for unit tests
  test_models.py
  test_comparison.py
  test_audio.py
  test_store.py
  test_renderer.py
  test_record.py
  test_check.py
  test_approve.py
pyproject.toml
.gitignore
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/snapshot/__init__.py`
- Create: `src/snapshot/commands/__init__.py`
- Create: `cases/snapshots.yaml`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `snapshot` CLI entry point resolvable via `python -m snapshot` and `snapshot` after install.

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling==1.25.0"]
build-backend = "hatchling.build"

[project]
name = "tts-snapshot-ci"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer==0.12.5",
    "pydantic==2.8.2",
    "elevenlabs==1.9.0",
    "pydub==0.25.1",
    "jinja2==3.1.4",
    "pyyaml==6.0.2",
    "diff-match-patch==20230430",
]

[project.scripts]
snapshot = "snapshot.cli:app"

[project.optional-dependencies]
dev = [
    "pytest==8.3.2",
    "pytest-mock==3.14.0",
    "ruff==0.6.1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/snapshot"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write .gitignore**

```gitignore
runs/
__pycache__/
*.pyc
.env
.venv/
dist/
*.egg-info/
.ruff_cache/
```

- [ ] **Step 3: Create package init files**

`src/snapshot/__init__.py` and `src/snapshot/commands/__init__.py` — both empty.

- [ ] **Step 4: Write starter snapshots.yaml**

```yaml
# cases/snapshots.yaml
cases:
  - id: hello_world
    source_text: "Hello world. This is a test."
    expected_transcript: "Hello world. This is a test."
    required_phrases:
      - "Hello world"
    voice_id: "21m00Tcm4TlvDq8ikWAM"   # Rachel - replace with your chosen voice
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 200
      leading_silence_ms: 150
      trailing_silence_ms: 150
```

- [ ] **Step 5: Create tests/__init__.py** — empty file.

- [ ] **Step 6: Install in editable mode**

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -e ".[dev]"
```

- [ ] **Step 7: Verify entry point resolves**

```bash
snapshot --help
```
Expected: typer help text (even if commands not yet wired).

- [ ] **Step 8: Commit**

```bash
git init
git add pyproject.toml .gitignore cases/ src/ tests/
git commit -m "chore: project scaffold"
```

---

### Task 2: Config And Result Models

**Files:**
- Create: `src/snapshot/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Tolerances(transcript_wer_threshold: float, duration_pct: float, duration_abs_ms: int, leading_silence_ms: int, trailing_silence_ms: int)`
  - `CaseConfig(id: str, source_text: str, expected_transcript: str, required_phrases: list[str], voice_id: str, model_id: str, output_format: str, tolerances: Tolerances)`
  - `SnapshotSuite(cases: list[CaseConfig])`
  - `RunState` enum: `PASS = "PASS"`, `REVIEW_REQUIRED = "REVIEW_REQUIRED"`, `ERROR = "ERROR"`
  - `CheckReason(check: str, detail: str)`
  - `CaseResult(case_id: str, state: RunState, reasons: list[CheckReason], baseline_transcript: str | None, candidate_transcript: str | None, baseline_duration_ms: int | None, candidate_duration_ms: int | None, baseline_leading_silence_ms: int | None, candidate_leading_silence_ms: int | None, baseline_trailing_silence_ms: int | None, candidate_trailing_silence_ms: int | None, generation_latency_ms: int | None, baseline_size_bytes: int | None, candidate_size_bytes: int | None, baseline_hash: str | None, candidate_hash: str | None)`
  - `RunResult(run_id: str, state: RunState, cases: list[CaseResult])`
  - `BaselineManifest(case_id: str, created_at: str, voice_id: str, model_id: str, output_format: str, source_text: str, expected_transcript: str, baseline_transcript: str, duration_ms: int, leading_silence_ms: int, trailing_silence_ms: int, size_bytes: int, audio_hash: str, approval_history: list[ApprovalRecord])`
  - `ApprovalRecord(approved_at: str, run_id: str, previous_hash: str, new_hash: str)`
  - `load_suite(path: Path) -> SnapshotSuite`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_models.py -v
```
Expected: ImportError or AttributeError.

- [ ] **Step 3: Implement models.py**

```python
# src/snapshot/models.py
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Any
import hashlib, json, yaml
from pydantic import BaseModel, model_validator


class RunState(str, Enum):
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"


class Tolerances(BaseModel):
    transcript_wer_threshold: float
    duration_pct: float
    duration_abs_ms: int
    leading_silence_ms: int
    trailing_silence_ms: int


class CaseConfig(BaseModel):
    id: str
    source_text: str
    expected_transcript: str
    required_phrases: list[str] = []
    voice_id: str
    model_id: str
    output_format: str
    tolerances: Tolerances


class SnapshotSuite(BaseModel):
    cases: list[CaseConfig]

    @model_validator(mode="after")
    def no_duplicate_ids(self) -> "SnapshotSuite":
        seen: set[str] = set()
        for c in self.cases:
            if c.id in seen:
                raise ValueError(f"Duplicate case id: {c.id!r}")
            seen.add(c.id)
        return self


class CheckReason(BaseModel):
    check: str
    detail: str


class CaseResult(BaseModel):
    case_id: str
    state: RunState
    reasons: list[CheckReason] = []
    baseline_transcript: str | None = None
    candidate_transcript: str | None = None
    baseline_duration_ms: int | None = None
    candidate_duration_ms: int | None = None
    baseline_leading_silence_ms: int | None = None
    candidate_leading_silence_ms: int | None = None
    baseline_trailing_silence_ms: int | None = None
    candidate_trailing_silence_ms: int | None = None
    generation_latency_ms: int | None = None
    baseline_size_bytes: int | None = None
    candidate_size_bytes: int | None = None
    baseline_hash: str | None = None
    candidate_hash: str | None = None


class RunResult(BaseModel):
    run_id: str
    state: RunState
    cases: list[CaseResult]


class ApprovalRecord(BaseModel):
    approved_at: str
    run_id: str
    previous_hash: str
    new_hash: str


class BaselineManifest(BaseModel):
    case_id: str
    created_at: str
    voice_id: str
    model_id: str
    output_format: str
    source_text: str
    expected_transcript: str
    baseline_transcript: str
    duration_ms: int
    leading_silence_ms: int
    trailing_silence_ms: int
    size_bytes: int
    audio_hash: str
    approval_history: list[ApprovalRecord] = []


def load_suite(path: Path) -> SnapshotSuite:
    if not path.exists():
        raise FileNotFoundError(f"Suite file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SnapshotSuite.model_validate(raw)


def audio_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_models.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/models.py tests/test_models.py
git commit -m "feat: config and result models"
```

---

### Task 3: Comparison Engine

**Files:**
- Create: `src/snapshot/comparison.py`
- Create: `tests/test_comparison.py`

**Interfaces:**
- Consumes: `Tolerances`, `RunState`, `CheckReason` from `snapshot.models`
- Produces:
  - `normalize_transcript(text: str) -> str` — lowercase, strip punctuation, collapse whitespace
  - `word_error_rate(reference: str, hypothesis: str) -> float`
  - `check_transcript_fidelity(expected: str, transcript: str, threshold: float) -> list[CheckReason]`
  - `check_required_phrases(phrases: list[str], transcript: str) -> list[CheckReason]`
  - `check_duration_drift(baseline_ms: int, candidate_ms: int, pct: float, abs_floor_ms: int) -> list[CheckReason]`
  - `check_silence_drift(baseline_leading_ms: int, candidate_leading_ms: int, baseline_trailing_ms: int, candidate_trailing_ms: int, leading_tol_ms: int, trailing_tol_ms: int) -> list[CheckReason]`
  - `aggregate_state(reasons: list[CheckReason], error: bool) -> RunState`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_comparison.py
import pytest
from snapshot.comparison import (
    normalize_transcript,
    word_error_rate,
    check_transcript_fidelity,
    check_required_phrases,
    check_duration_drift,
    check_silence_drift,
    aggregate_state,
)
from snapshot.models import RunState


def test_normalize_strips_punctuation():
    assert normalize_transcript("Hello, World!") == "hello world"


def test_normalize_collapses_whitespace():
    assert normalize_transcript("  hello   world  ") == "hello world"


def test_wer_identical():
    assert word_error_rate("hello world", "hello world") == 0.0


def test_wer_one_substitution():
    # reference: "hello world" (2 words), hypothesis replaces 1
    rate = word_error_rate("hello world", "hello earth")
    assert abs(rate - 0.5) < 0.01


def test_wer_all_wrong():
    rate = word_error_rate("hello world", "foo bar")
    assert rate == 1.0


def test_fidelity_pass():
    reasons = check_transcript_fidelity("hello world", "hello world", threshold=0.15)
    assert reasons == []


def test_fidelity_review_required():
    reasons = check_transcript_fidelity("hello world test", "goodbye world test", threshold=0.15)
    assert any(r.check == "transcript_fidelity" for r in reasons)


def test_required_phrases_all_present():
    reasons = check_required_phrases(["hello", "world"], "hello world test")
    assert reasons == []


def test_required_phrases_missing():
    reasons = check_required_phrases(["missing_phrase"], "hello world")
    assert any(r.check == "required_phrase" for r in reasons)
    assert "missing_phrase" in reasons[0].detail


def test_required_phrases_empty_list():
    assert check_required_phrases([], "anything") == []


def test_duration_drift_within_pct():
    # baseline 1000ms, candidate 1050ms, 10% tolerance = 100ms allowed
    reasons = check_duration_drift(1000, 1050, pct=0.10, abs_floor_ms=200)
    assert reasons == []


def test_duration_drift_within_abs_floor():
    # baseline 100ms, candidate 115ms; 10% of 100 = 10ms < floor 200ms, floor wins
    reasons = check_duration_drift(100, 115, pct=0.10, abs_floor_ms=200)
    assert reasons == []


def test_duration_drift_exceeds_both():
    # baseline 1000ms, candidate 1500ms, 10% = 100ms, floor 200ms — both exceeded
    reasons = check_duration_drift(1000, 1500, pct=0.10, abs_floor_ms=200)
    assert any(r.check == "duration_drift" for r in reasons)


def test_silence_drift_within_tolerance():
    reasons = check_silence_drift(100, 120, 100, 110, leading_tol_ms=150, trailing_tol_ms=150)
    assert reasons == []


def test_leading_silence_exceeds():
    reasons = check_silence_drift(100, 400, 100, 100, leading_tol_ms=150, trailing_tol_ms=150)
    assert any(r.check == "leading_silence_drift" for r in reasons)


def test_trailing_silence_exceeds():
    reasons = check_silence_drift(100, 100, 100, 400, leading_tol_ms=150, trailing_tol_ms=150)
    assert any(r.check == "trailing_silence_drift" for r in reasons)


def test_aggregate_pass():
    assert aggregate_state([], error=False) == RunState.PASS


def test_aggregate_review():
    from snapshot.models import CheckReason
    r = CheckReason(check="duration_drift", detail="delta 500ms")
    assert aggregate_state([r], error=False) == RunState.REVIEW_REQUIRED


def test_aggregate_error_dominates():
    from snapshot.models import CheckReason
    r = CheckReason(check="duration_drift", detail="delta 500ms")
    assert aggregate_state([r], error=True) == RunState.ERROR


def test_aggregate_error_no_reasons():
    assert aggregate_state([], error=True) == RunState.ERROR
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_comparison.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement comparison.py**

```python
# src/snapshot/comparison.py
from __future__ import annotations
import re
from snapshot.models import CheckReason, RunState


def normalize_transcript(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein edit distance at word level divided by reference length."""
    ref = normalize_transcript(reference).split()
    hyp = normalize_transcript(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    # DP edit distance
    d = list(range(len(hyp) + 1))
    for i, rw in enumerate(ref):
        prev = d[:]
        d[0] = i + 1
        for j, hw in enumerate(hyp):
            d[j + 1] = min(prev[j] + (0 if rw == hw else 1), d[j] + 1, prev[j + 1] + 1)
    return d[len(hyp)] / len(ref)


def check_transcript_fidelity(
    expected: str, transcript: str, threshold: float
) -> list[CheckReason]:
    wer = word_error_rate(expected, transcript)
    if wer > threshold:
        return [CheckReason(
            check="transcript_fidelity",
            detail=f"WER {wer:.2%} exceeds threshold {threshold:.2%}",
        )]
    return []


def check_required_phrases(phrases: list[str], transcript: str) -> list[CheckReason]:
    norm = normalize_transcript(transcript)
    reasons: list[CheckReason] = []
    for phrase in phrases:
        if normalize_transcript(phrase) not in norm:
            reasons.append(CheckReason(
                check="required_phrase",
                detail=f"Required phrase not found: {phrase!r}",
            ))
    return reasons


def check_duration_drift(
    baseline_ms: int, candidate_ms: int, pct: float, abs_floor_ms: int
) -> list[CheckReason]:
    allowed = max(baseline_ms * pct, abs_floor_ms)
    delta = abs(candidate_ms - baseline_ms)
    if delta > allowed:
        return [CheckReason(
            check="duration_drift",
            detail=(
                f"Delta {delta}ms exceeds allowed "
                f"{allowed:.0f}ms (max({baseline_ms}ms*{pct:.0%}, {abs_floor_ms}ms))"
            ),
        )]
    return []


def check_silence_drift(
    baseline_leading_ms: int,
    candidate_leading_ms: int,
    baseline_trailing_ms: int,
    candidate_trailing_ms: int,
    leading_tol_ms: int,
    trailing_tol_ms: int,
) -> list[CheckReason]:
    reasons: list[CheckReason] = []
    lead_delta = abs(candidate_leading_ms - baseline_leading_ms)
    if lead_delta > leading_tol_ms:
        reasons.append(CheckReason(
            check="leading_silence_drift",
            detail=f"Leading silence delta {lead_delta}ms exceeds tolerance {leading_tol_ms}ms",
        ))
    trail_delta = abs(candidate_trailing_ms - baseline_trailing_ms)
    if trail_delta > trailing_tol_ms:
        reasons.append(CheckReason(
            check="trailing_silence_drift",
            detail=f"Trailing silence delta {trail_delta}ms exceeds tolerance {trailing_tol_ms}ms",
        ))
    return reasons


def aggregate_state(reasons: list[CheckReason], error: bool) -> RunState:
    if error:
        return RunState.ERROR
    if reasons:
        return RunState.REVIEW_REQUIRED
    return RunState.PASS
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_comparison.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/comparison.py tests/test_comparison.py
git commit -m "feat: pure comparison engine"
```

---

### Task 4: Audio Analyzer

**Files:**
- Create: `src/snapshot/audio.py`
- Create: `tests/fixtures/` (two tiny synthetic mp3 clips generated inline during test setup)
- Create: `tests/test_audio.py`

**Interfaces:**
- Consumes: nothing from this project
- Produces:
  - `SILENCE_AMPLITUDE_THRESHOLD: float = -50.0`  (dBFS; documented constant)
  - `SILENCE_MIN_WINDOW_MS: int = 50`
  - `AudioMeasurements(duration_ms: int, leading_silence_ms: int, trailing_silence_ms: int, size_bytes: int, audio_hash: str)`
  - `measure_audio(path: Path) -> AudioMeasurements`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_audio.py
import struct, wave
from pathlib import Path
import pytest
from snapshot.audio import measure_audio, AudioMeasurements, SILENCE_AMPLITUDE_THRESHOLD


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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_audio.py -v
```

- [ ] **Step 3: Implement audio.py**

```python
# src/snapshot/audio.py
from __future__ import annotations
import hashlib
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
    seg = AudioSegment.from_file(str(path))
    return AudioMeasurements(
        duration_ms=int(len(seg)),
        leading_silence_ms=_leading_silence_ms(seg),
        trailing_silence_ms=_trailing_silence_ms(seg),
        size_bytes=len(data),
        audio_hash=hashlib.sha256(data).hexdigest(),
    )
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_audio.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/audio.py tests/test_audio.py
git commit -m "feat: audio analyzer with documented silence constants"
```

---

### Task 5: ElevenLabs Adapter

**Files:**
- Create: `src/snapshot/adapters.py`
- Create: `tests/test_adapters_fake.py`

**Interfaces:**
- Consumes: `CaseConfig` from `snapshot.models`
- Produces:
  - `TTSResult(audio: bytes, latency_ms: int, voice_id: str, model_id: str, output_format: str)`
  - `STTResult(transcript: str)`
  - `AdapterProtocol` — typing.Protocol with `generate_speech(case: CaseConfig) -> TTSResult` and `transcribe(audio: bytes, language_code: str | None) -> STTResult`
  - `ElevenLabsAdapter(api_key: str)` implementing `AdapterProtocol`
  - `FakeAdapter(speech_bytes: bytes, transcript: str)` for tests — returns fixed values

- [ ] **Step 1: Write failing tests using FakeAdapter**

```python
# tests/test_adapters_fake.py
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
        tolerances=Tolerances(0.15, 0.10, 200, 150, 150),
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_adapters_fake.py -v
```

- [ ] **Step 3: Implement adapters.py**

```python
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
        if language_code:
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
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_adapters_fake.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/adapters.py tests/test_adapters_fake.py
git commit -m "feat: ElevenLabs adapter with FakeAdapter for tests"
```

---

### Task 6: Artifact Store

**Files:**
- Create: `src/snapshot/store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Consumes: `BaselineManifest`, `ApprovalRecord`, `CaseResult`, `RunResult`, `RunState` from `snapshot.models`; `AudioMeasurements` from `snapshot.audio`
- Produces:
  - `ArtifactStore(snapshots_dir: Path, runs_dir: Path)`
    - `baseline_exists(case_id: str) -> bool`
    - `read_baseline_audio(case_id: str) -> bytes`
    - `read_baseline_manifest(case_id: str) -> BaselineManifest`
    - `write_baseline(case_id: str, audio: bytes, manifest: BaselineManifest) -> None`  — raises if exists
    - `new_run_id() -> str`  — ISO timestamp + 6-char hex
    - `write_candidate(run_id: str, case_id: str, audio: bytes) -> Path`
    - `read_candidate(run_id: str, case_id: str) -> bytes`
    - `write_run_results(run_id: str, result: RunResult) -> None`
    - `read_run_results(run_id: str) -> RunResult`
    - `write_report(run_id: str, html: str) -> Path`
    - `promote_candidate_to_baseline(run_id: str, case_id: str, new_manifest: BaselineManifest) -> None`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_store.py -v
```

- [ ] **Step 3: Implement store.py**

```python
# src/snapshot/store.py
from __future__ import annotations
import json, secrets
from datetime import datetime, timezone
from pathlib import Path
from snapshot.models import BaselineManifest, RunResult


class ArtifactStore:
    def __init__(self, snapshots_dir: Path, runs_dir: Path) -> None:
        self._snap = snapshots_dir
        self._runs = runs_dir

    def _case_dir(self, case_id: str) -> Path:
        return self._snap / case_id

    def _run_dir(self, run_id: str) -> Path:
        return self._runs / run_id

    def baseline_exists(self, case_id: str) -> bool:
        return (self._case_dir(case_id) / "baseline.mp3").exists()

    def read_baseline_audio(self, case_id: str) -> bytes:
        return (self._case_dir(case_id) / "baseline.mp3").read_bytes()

    def read_baseline_manifest(self, case_id: str) -> BaselineManifest:
        raw = (self._case_dir(case_id) / "manifest.json").read_text(encoding="utf-8")
        return BaselineManifest.model_validate_json(raw)

    def write_baseline(self, case_id: str, audio: bytes, manifest: BaselineManifest) -> None:
        dest = self._case_dir(case_id) / "baseline.mp3"
        if dest.exists():
            raise FileExistsError(f"Baseline already exists for {case_id!r}. Use check -> approve to replace it.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        (self._case_dir(case_id) / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )

    def new_run_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{secrets.token_hex(3)}"

    def write_candidate(self, run_id: str, case_id: str, audio: bytes) -> Path:
        dest = self._run_dir(run_id) / "candidates" / f"{case_id}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        return dest

    def read_candidate(self, run_id: str, case_id: str) -> bytes:
        return (self._run_dir(run_id) / "candidates" / f"{case_id}.mp3").read_bytes()

    def write_run_results(self, run_id: str, result: RunResult) -> None:
        dest = self._run_dir(run_id) / "results.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def read_run_results(self, run_id: str) -> RunResult:
        raw = (self._run_dir(run_id) / "results.json").read_text(encoding="utf-8")
        return RunResult.model_validate_json(raw)

    def write_report(self, run_id: str, html: str) -> Path:
        dest = self._run_dir(run_id) / "report.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        return dest

    def promote_candidate_to_baseline(
        self, run_id: str, case_id: str, new_manifest: BaselineManifest
    ) -> None:
        audio = self.read_candidate(run_id, case_id)
        dest_audio = self._case_dir(case_id) / "baseline.mp3"
        dest_audio.parent.mkdir(parents=True, exist_ok=True)
        dest_audio.write_bytes(audio)
        (self._case_dir(case_id) / "manifest.json").write_text(
            new_manifest.model_dump_json(indent=2), encoding="utf-8"
        )
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/store.py tests/test_store.py
git commit -m "feat: artifact store with baseline lifecycle"
```

---

### Task 7: Record Command

**Files:**
- Create: `src/snapshot/commands/record.py`
- Create: `tests/test_record.py`

**Interfaces:**
- Consumes: `load_suite`, `CaseConfig` from `snapshot.models`; `ElevenLabsAdapter`, `FakeAdapter`, `TTSResult` from `snapshot.adapters`; `measure_audio` from `snapshot.audio`; `ArtifactStore` from `snapshot.store`; `audio_hash` from `snapshot.models`
- Produces:
  - `record_suite(suite_path: Path, snapshots_dir: Path, runs_dir: Path, adapter: AdapterProtocol) -> list[str]`
    — returns list of recorded case IDs; skips existing baselines (prints skip message); raises on API error

- [ ] **Step 1: Write failing tests**

```python
# tests/test_record.py
import struct, wave, math
from pathlib import Path
import pytest
from snapshot.commands.record import record_suite
from snapshot.adapters import FakeAdapter
from snapshot.store import ArtifactStore


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


def test_record_creates_baseline(tmp_path):
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


def test_record_skips_existing_baseline(tmp_path):
    suite_path = _write_suite(tmp_path)
    audio = _make_wav()
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello.")
    # record once
    record_suite(suite_path, tmp_path / "snapshots", tmp_path / "runs", adapter)
    # record again — should skip without raising
    recorded = record_suite(suite_path, tmp_path / "snapshots", tmp_path / "runs", adapter)
    assert recorded == []
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_record.py -v
```

- [ ] **Step 3: Implement record.py**

```python
# src/snapshot/commands/record.py
from __future__ import annotations
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from snapshot.adapters import AdapterProtocol
from snapshot.audio import measure_audio
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

        # write to a temp file so pydub can measure it
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_bytes(tts.audio)

        try:
            measurements = measure_audio(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

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
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_record.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/commands/record.py tests/test_record.py
git commit -m "feat: record command"
```

---

### Task 8: Check Command

**Files:**
- Create: `src/snapshot/commands/check.py`
- Create: `tests/test_check.py`

**Interfaces:**
- Consumes: all prior modules
- Produces:
  - `check_suite(suite_path: Path, snapshots_dir: Path, runs_dir: Path, adapter: AdapterProtocol) -> RunResult`
    — generates candidates, runs four comparisons, aggregates state, writes results.json; does NOT write report (renderer handles that)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_check.py
import struct, wave, math, io
from pathlib import Path
import pytest
from snapshot.commands.record import record_suite
from snapshot.commands.check import check_suite
from snapshot.adapters import FakeAdapter
from snapshot.models import RunState


def _wav(duration_ms: int = 400, freq: int = 440, amp: float = 0.5) -> bytes:
    sr = 44100
    n = int(sr * duration_ms / 1000)
    frames = b"".join(
        struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr)))
        for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(frames)
    return buf.getvalue()


def _suite(tmp_path: Path) -> Path:
    p = tmp_path / "snapshots.yaml"
    p.write_text("""
cases:
  - id: c1
    source_text: "Hello world."
    expected_transcript: "Hello world."
    required_phrases:
      - "Hello world"
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


def _dirs(tmp_path: Path):
    return tmp_path / "snapshots", tmp_path / "runs"


def test_check_pass(tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, adapter)
    result = check_suite(suite, snap, runs, adapter)
    assert result.state == RunState.PASS
    assert all(c.state == RunState.PASS for c in result.cases)


def test_check_review_required_on_missing_phrase(tmp_path):
    audio = _wav(400)
    # baseline has "Hello world.", candidate transcript missing required phrase
    base_adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, base_adapter)

    # now check with a candidate that drops the required phrase
    cand_adapter = FakeAdapter(speech_bytes=audio, transcript="Goodbye earth.")
    result = check_suite(suite, snap, runs, cand_adapter)
    assert result.state == RunState.REVIEW_REQUIRED


def test_check_does_not_mutate_baseline(tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    record_suite(suite, snap, runs, adapter)
    original = (snap / "c1" / "baseline.mp3").read_bytes()
    check_suite(suite, snap, runs, adapter)
    assert (snap / "c1" / "baseline.mp3").read_bytes() == original


def test_check_error_when_no_baseline(tmp_path):
    audio = _wav(400)
    adapter = FakeAdapter(speech_bytes=audio, transcript="Hello world.")
    suite = _suite(tmp_path)
    snap, runs = _dirs(tmp_path)
    # intentionally skip record step
    result = check_suite(suite, snap, runs, adapter)
    assert result.state == RunState.ERROR
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_check.py -v
```

- [ ] **Step 3: Implement check.py**

```python
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
        run_id_tmp = "tmp"  # candidates written by caller after run_id is created
        # write candidate to a temp file for measurement
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_bytes(tts.audio)
        try:
            cand_m = measure_audio(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

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
        # write candidate audio if generation succeeded
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
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_check.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/commands/check.py tests/test_check.py
git commit -m "feat: check command"
```

---

### Task 9: HTML Report Renderer

**Files:**
- Create: `src/snapshot/renderer.py`
- Create: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `RunResult`, `CaseResult`, `RunState`, `CheckReason` from `snapshot.models`
- Produces:
  - `render_report(result: RunResult, baseline_audio: dict[str, bytes], candidate_audio: dict[str, bytes]) -> str`
    — returns self-contained HTML string; audio embedded as base64 data URIs so the file opens without a server

- [ ] **Step 1: Write failing tests**

```python
# tests/test_renderer.py
from snapshot.renderer import render_report
from snapshot.models import RunResult, CaseResult, RunState, CheckReason


def _result(state: RunState = RunState.PASS) -> RunResult:
    return RunResult(
        run_id="20260817T000000Z-abc123",
        state=state,
        cases=[
            CaseResult(
                case_id="c1",
                state=state,
                reasons=[CheckReason(check="duration_drift", detail="delta 500ms")]
                        if state == RunState.REVIEW_REQUIRED else [],
                baseline_transcript="Hello world.",
                candidate_transcript="Hello world.",
                baseline_duration_ms=500,
                candidate_duration_ms=1000,
                baseline_leading_silence_ms=50,
                candidate_leading_silence_ms=50,
                baseline_trailing_silence_ms=50,
                candidate_trailing_silence_ms=50,
                generation_latency_ms=320,
                baseline_size_bytes=1024,
                candidate_size_bytes=2048,
                baseline_hash="aaa",
                candidate_hash="bbb",
            )
        ],
    )


def test_render_returns_html_string():
    html = render_report(_result(), baseline_audio={"c1": b"FAKE"}, candidate_audio={"c1": b"FAKE"})
    assert isinstance(html, str)
    assert "<html" in html.lower()


def test_render_contains_run_state():
    html = render_report(_result(RunState.PASS), {}, {})
    assert "PASS" in html


def test_render_review_contains_reasons():
    html = render_report(
        _result(RunState.REVIEW_REQUIRED),
        baseline_audio={"c1": b"FAKE"},
        candidate_audio={"c1": b"FAKE"},
    )
    assert "duration_drift" in html
    assert "REVIEW_REQUIRED" in html


def test_render_embeds_audio_as_base64():
    html = render_report(
        _result(),
        baseline_audio={"c1": b"AUDIO"},
        candidate_audio={"c1": b"AUDIO"},
    )
    assert "data:audio" in html


def test_render_shows_both_transcripts():
    html = render_report(
        _result(),
        baseline_audio={"c1": b"AUDIO"},
        candidate_audio={"c1": b"AUDIO"},
    )
    assert "Hello world." in html


def test_only_three_state_labels_appear():
    html = render_report(_result(RunState.REVIEW_REQUIRED), {}, {})
    for forbidden in ["FAIL", "WARN", "WARNING"]:
        assert forbidden not in html
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_renderer.py -v
```

- [ ] **Step 3: Implement renderer.py**

```python
# src/snapshot/renderer.py
from __future__ import annotations
import base64
from jinja2 import Environment, BaseLoader
from snapshot.models import RunResult, RunState

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TTS Snapshot CI — {{ result.run_id }}</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.4rem; }
  .state-PASS { color: #1a7f37; font-weight: bold; }
  .state-REVIEW_REQUIRED { color: #9a5c00; font-weight: bold; }
  .state-ERROR { color: #cf222e; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
  th, td { padding: 0.5rem 0.75rem; border: 1px solid #d0d7de; text-align: left; vertical-align: top; }
  th { background: #f6f8fa; }
  audio { width: 100%; max-width: 320px; }
  .reasons { color: #9a5c00; font-size: 0.85rem; }
  .meta { font-size: 0.8rem; color: #57606a; }
  .diff-del { background: #ffd7d5; }
  .diff-ins { background: #ccffd8; }
  details summary { cursor: pointer; font-size: 0.85rem; color: #0969da; }
</style>
</head>
<body>
<h1>TTS Snapshot CI</h1>
<p>Run: <code>{{ result.run_id }}</code> &nbsp;|&nbsp;
   State: <span class="state-{{ result.state.value }}">{{ result.state.value }}</span></p>

<table>
<thead>
<tr>
  <th>Case</th><th>State</th><th>Source / Expected</th>
  <th>Baseline transcript</th><th>Candidate transcript</th>
  <th>Baseline audio</th><th>Candidate audio</th>
  <th>Measurements</th><th>Reasons</th>
</tr>
</thead>
<tbody>
{% for case in result.cases %}
<tr>
  <td><code>{{ case.case_id }}</code></td>
  <td><span class="state-{{ case.state.value }}">{{ case.state.value }}</span></td>
  <td class="meta">{{ case_configs[case.case_id].source_text if case_configs and case.case_id in case_configs else "" }}</td>
  <td>{{ case.baseline_transcript or "—" }}</td>
  <td>{{ case.candidate_transcript or "—" }}</td>
  <td>
    {% if baseline_audio[case.case_id] %}
    <audio controls src="data:audio/mpeg;base64,{{ baseline_audio[case.case_id] }}"></audio>
    {% else %}—{% endif %}
  </td>
  <td>
    {% if candidate_audio[case.case_id] %}
    <audio controls src="data:audio/mpeg;base64,{{ candidate_audio[case.case_id] }}"></audio>
    {% else %}—{% endif %}
  </td>
  <td class="meta">
    duration: {{ case.baseline_duration_ms or "?" }}ms → {{ case.candidate_duration_ms or "?" }}ms<br>
    lead sil: {{ case.baseline_leading_silence_ms or "?" }}ms → {{ case.candidate_leading_silence_ms or "?" }}ms<br>
    trail sil: {{ case.baseline_trailing_silence_ms or "?" }}ms → {{ case.candidate_trailing_silence_ms or "?" }}ms<br>
    latency: {{ case.generation_latency_ms or "?" }}ms<br>
    <details><summary>hashes</summary>
    base: {{ case.baseline_hash or "?" }}<br>cand: {{ case.candidate_hash or "?" }}
    </details>
  </td>
  <td>
    {% if case.reasons %}
    <ul class="reasons">
      {% for r in case.reasons %}<li><strong>{{ r.check }}</strong>: {{ r.detail }}</li>{% endfor %}
    </ul>
    {% else %}—{% endif %}
  </td>
</tr>
{% endfor %}
</tbody>
</table>
<p class="meta" style="margin-top:2rem">
  <em>REVIEW_REQUIRED requests inspection; it does not assert a TTS defect.
  ElevenLabs STT errors can appear as transcript fidelity differences.
  Listen to both clips before assigning cause.</em>
</p>
</body>
</html>"""


def render_report(
    result: RunResult,
    baseline_audio: dict[str, bytes],
    candidate_audio: dict[str, bytes],
    case_configs: dict | None = None,
) -> str:
    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(_TEMPLATE)

    def _b64(d: dict[str, bytes], key: str) -> str:
        data = d.get(key, b"")
        return base64.b64encode(data).decode() if data else ""

    b64_baseline = {k: _b64(baseline_audio, k) for k in [c.case_id for c in result.cases]}
    b64_candidate = {k: _b64(candidate_audio, k) for k in [c.case_id for c in result.cases]}

    return tmpl.render(
        result=result,
        baseline_audio=b64_baseline,
        candidate_audio=b64_candidate,
        case_configs=case_configs or {},
    )
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_renderer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/renderer.py tests/test_renderer.py
git commit -m "feat: HTML report renderer with embedded audio"
```

---

### Task 10: Approve Command

**Files:**
- Create: `src/snapshot/commands/approve.py`
- Create: `tests/test_approve.py`

**Interfaces:**
- Consumes: `ArtifactStore` from `snapshot.store`; `BaselineManifest`, `ApprovalRecord`, `RunState`, `audio_hash` from `snapshot.models`
- Produces:
  - `approve_cases(run_id: str, case_ids: list[str], snapshots_dir: Path, runs_dir: Path) -> list[str]`
    — promotes named candidates; returns approved case IDs; raises `ValueError` for ERROR candidates

- [ ] **Step 1: Write failing tests**

```python
# tests/test_approve.py
import struct, wave, math, io
from pathlib import Path
import pytest
from snapshot.commands.record import record_suite
from snapshot.commands.check import check_suite
from snapshot.commands.approve import approve_cases
from snapshot.adapters import FakeAdapter
from snapshot.models import RunState


def _wav(duration_ms: int = 300) -> bytes:
    sr, n = 44100, int(44100 * duration_ms / 1000)
    frames = b"".join(
        struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / sr)))
        for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(frames)
    return buf.getvalue()


def _suite(tmp_path: Path) -> Path:
    p = tmp_path / "snapshots.yaml"
    p.write_text("""
cases:
  - id: c1
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


def test_approve_promotes_candidate(tmp_path):
    audio_v1 = _wav(300)
    audio_v2 = _wav(350)
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)

    # baseline with v1
    record_suite(suite, snap, runs, FakeAdapter(audio_v1, "Hello."))
    original = (snap / "c1" / "baseline.mp3").read_bytes()

    # check with v2 — gets REVIEW_REQUIRED or PASS; either can be approved
    result = check_suite(suite, snap, runs, FakeAdapter(audio_v2, "Hello."))
    run_id = result.run_id

    approved = approve_cases(run_id, ["c1"], snap, runs)
    assert "c1" in approved
    assert (snap / "c1" / "baseline.mp3").read_bytes() != original

    # manifest should have one approval record
    from snapshot.store import ArtifactStore
    store = ArtifactStore(snap, runs)
    manifest = store.read_baseline_manifest("c1")
    assert len(manifest.approval_history) == 1
    assert manifest.approval_history[0].run_id == run_id


def test_approve_rejects_error_candidate(tmp_path):
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)
    # skip record — check will ERROR
    result = check_suite(suite, snap, runs, FakeAdapter(_wav(), "Hello."))
    run_id = result.run_id
    with pytest.raises(ValueError, match="ERROR"):
        approve_cases(run_id, ["c1"], snap, runs)


def test_approve_rejects_unknown_case(tmp_path):
    audio = _wav()
    snap, runs = tmp_path / "snapshots", tmp_path / "runs"
    suite = _suite(tmp_path)
    record_suite(suite, snap, runs, FakeAdapter(audio, "Hello."))
    result = check_suite(suite, snap, runs, FakeAdapter(audio, "Hello."))
    with pytest.raises(ValueError, match="not found"):
        approve_cases(result.run_id, ["nonexistent"], snap, runs)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_approve.py -v
```

- [ ] **Step 3: Implement approve.py**

```python
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
    store = ArtifactStore(snapshots_dir=snapshots_dir, runs_dir=runs_dir)
    run_result = store.read_run_results(run_id)

    # index run results by case id
    by_id = {c.case_id: c for c in run_result.cases}

    approved: list[str] = []
    for case_id in case_ids:
        if case_id not in by_id:
            raise ValueError(f"Case {case_id!r} not found in run {run_id!r}.")
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
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_approve.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snapshot/commands/approve.py tests/test_approve.py
git commit -m "feat: approve command with audit trail"
```

---

### Task 11: CLI Wiring

**Files:**
- Create: `src/snapshot/cli.py`

**Interfaces:**
- Consumes: all command modules; `ElevenLabsAdapter` from `snapshot.adapters`
- Produces: `snapshot record`, `snapshot check`, `snapshot approve` as typer commands with correct exit codes

- [ ] **Step 1: Implement cli.py**

No test file for this task — the CLI is exercised in Task 12 end-to-end. Verify manually.

```python
# src/snapshot/cli.py
from __future__ import annotations
import os, sys
from pathlib import Path
import typer
from snapshot.models import RunState

app = typer.Typer(name="snapshot", help="TTS Snapshot CI — detect review-worthy speech changes.")

_DEFAULT_SUITE = Path("cases/snapshots.yaml")
_DEFAULT_SNAPSHOTS = Path("snapshots")
_DEFAULT_RUNS = Path("runs")


def _adapter():
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        typer.echo("ERROR: ELEVENLABS_API_KEY environment variable is not set.", err=True)
        raise typer.Exit(2)
    from snapshot.adapters import ElevenLabsAdapter
    return ElevenLabsAdapter(api_key=api_key)


@app.command()
def record(
    suite: Path = typer.Option(_DEFAULT_SUITE, "--suite", "-s", help="Path to snapshots.yaml"),
    snapshots_dir: Path = typer.Option(_DEFAULT_SNAPSHOTS, "--snapshots-dir"),
    runs_dir: Path = typer.Option(_DEFAULT_RUNS, "--runs-dir"),
) -> None:
    """Generate missing baseline audio for all cases in the suite."""
    from snapshot.commands.record import record_suite
    adapter = _adapter()
    try:
        recorded = record_suite(suite, snapshots_dir, runs_dir, adapter)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    if recorded:
        typer.echo(f"Recorded {len(recorded)} baseline(s): {', '.join(recorded)}")
    else:
        typer.echo("All baselines already exist. Nothing recorded.")


@app.command()
def check(
    suite: Path = typer.Option(_DEFAULT_SUITE, "--suite", "-s"),
    snapshots_dir: Path = typer.Option(_DEFAULT_SNAPSHOTS, "--snapshots-dir"),
    runs_dir: Path = typer.Option(_DEFAULT_RUNS, "--runs-dir"),
) -> None:
    """Generate candidates, run comparisons, and write a report."""
    from snapshot.commands.check import check_suite
    from snapshot.renderer import render_report
    from snapshot.store import ArtifactStore

    adapter = _adapter()
    try:
        result = check_suite(suite, snapshots_dir, runs_dir, adapter)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)

    store = ArtifactStore(snapshots_dir, runs_dir)

    # collect audio for report
    baseline_audio: dict[str, bytes] = {}
    candidate_audio: dict[str, bytes] = {}
    for cr in result.cases:
        if store.baseline_exists(cr.case_id):
            try:
                baseline_audio[cr.case_id] = store.read_baseline_audio(cr.case_id)
            except Exception:
                pass
        try:
            candidate_audio[cr.case_id] = store.read_candidate(result.run_id, cr.case_id)
        except Exception:
            pass

    html = render_report(result, baseline_audio, candidate_audio)
    report_path = store.write_report(result.run_id, html)

    typer.echo(f"\nRun:    {result.run_id}")
    typer.echo(f"State:  {result.state.value}")
    typer.echo(f"Report: {report_path}")

    for cr in result.cases:
        line = f"  {cr.case_id}: {cr.state.value}"
        if cr.reasons:
            line += " — " + "; ".join(f"{r.check}: {r.detail}" for r in cr.reasons)
        typer.echo(line)

    exit_map = {RunState.PASS: 0, RunState.REVIEW_REQUIRED: 1, RunState.ERROR: 2}
    raise typer.Exit(exit_map[result.state])


@app.command()
def approve(
    run_id: str = typer.Argument(..., help="Run ID to approve candidates from"),
    case_ids: list[str] = typer.Argument(..., help="One or more case IDs to approve"),
    snapshots_dir: Path = typer.Option(_DEFAULT_SNAPSHOTS, "--snapshots-dir"),
    runs_dir: Path = typer.Option(_DEFAULT_RUNS, "--runs-dir"),
) -> None:
    """Promote named candidates from a completed run into approved baselines."""
    from snapshot.commands.approve import approve_cases
    try:
        approved = approve_cases(run_id, list(case_ids), snapshots_dir, runs_dir)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(f"Approved {len(approved)} case(s): {', '.join(approved)}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Verify commands resolve**

```bash
snapshot --help
snapshot record --help
snapshot check --help
snapshot approve --help
```
Expected: all four print usage text without ImportError.

- [ ] **Step 3: Run full unit test suite**

```bash
pytest -v
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/snapshot/cli.py
git commit -m "feat: CLI wiring for record, check, approve"
```

---

### Task 12: End-To-End Verification Gate

**Goal:** Run a live ElevenLabs suite that demonstrates PASS, REVIEW_REQUIRED, and ERROR with verified exit codes, then inspect the report in a browser. This is the CLI completion gate — no Action YAML may be written until every item below is checked.

**Prerequisite:** `ELEVENLABS_API_KEY` must be set in your shell.

- [ ] **Step 1: Extend snapshots.yaml with three deliberate cases**

Edit `cases/snapshots.yaml` to include these three cases. Choose a voice ID from your ElevenLabs account.

```yaml
cases:
  # Case 1: clean — expect PASS
  - id: clean_greeting
    source_text: "Hello. This is a TTS Snapshot CI verification test."
    expected_transcript: "Hello. This is a TTS Snapshot CI verification test."
    required_phrases:
      - "TTS Snapshot CI"
    voice_id: "21m00Tcm4TlvDq8ikWAM"   # Rachel — replace with yours
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 300
      leading_silence_ms: 200
      trailing_silence_ms: 200

  # Case 2: required-phrase trip — expect REVIEW_REQUIRED after editing source_text
  - id: phrase_guard
    source_text: "Please contact support at support@example.com for assistance."
    expected_transcript: "Please contact support at support@example.com for assistance."
    required_phrases:
      - "support@example.com"
    voice_id: "21m00Tcm4TlvDq8ikWAM"
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 300
      leading_silence_ms: 200
      trailing_silence_ms: 200

  # Case 3: bad voice ID — expect ERROR
  - id: forced_error
    source_text: "This case intentionally uses a bad voice ID."
    expected_transcript: "This case intentionally uses a bad voice ID."
    required_phrases: []
    voice_id: "INVALID_VOICE_ID_FOR_ERROR"
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 300
      leading_silence_ms: 200
      trailing_silence_ms: 200
```

- [ ] **Step 2: Record baselines for the two valid cases only**

The `forced_error` case will ERROR on record, which is expected. Record will skip it with an error message.

```bash
snapshot record
```
Expected: `clean_greeting` and `phrase_guard` baselines written. `forced_error` prints an error.

- [ ] **Step 3: Run check — expect PASS for clean_greeting**

```bash
snapshot check
echo "Exit: $LASTEXITCODE"
```
Expected: `clean_greeting` → PASS, `phrase_guard` → PASS or REVIEW_REQUIRED, `forced_error` → ERROR.
Run state should be ERROR (ERROR dominates). Exit code should be 2.

- [ ] **Step 4: Induce REVIEW_REQUIRED on phrase_guard**

Edit `cases/snapshots.yaml` — change `phrase_guard` source_text to remove the email address:

```yaml
    source_text: "Please contact support for assistance."
```

Then run check again:

```bash
snapshot check
echo "Exit: $LASTEXITCODE"
```
Expected: `phrase_guard` → REVIEW_REQUIRED (required phrase missing from transcript).

- [ ] **Step 5: Verify exit codes**

```bash
# After a PASS-only run (temporarily remove forced_error case, restore phrase_guard text):
snapshot check; echo "Exit should be 0: $LASTEXITCODE"

# After the REVIEW_REQUIRED run:
snapshot check; echo "Exit should be 1: $LASTEXITCODE"

# After re-adding forced_error:
snapshot check; echo "Exit should be 2: $LASTEXITCODE"
```

- [ ] **Step 6: Open the report in a browser and verify all required elements**

Find the latest run directory:

```bash
ls runs/
```

Open `runs/<latest-run-id>/report.html` in your browser. Confirm all of the following are visible:

- [ ] source text for each case
- [ ] expected transcript for each case
- [ ] baseline STT transcript
- [ ] candidate STT transcript
- [ ] highlighted transcript differences
- [ ] duration and silence measurements
- [ ] generation latency (informational)
- [ ] baseline audio player (plays audio)
- [ ] candidate audio player (plays audio)
- [ ] case state labels using only PASS / REVIEW_REQUIRED / ERROR
- [ ] STT limitation notice at the bottom of the report

- [ ] **Step 7: Run approve on a REVIEW_REQUIRED candidate**

```bash
snapshot approve <run-id-from-step-4> phrase_guard
```
Expected: manifest updated, approval history contains one record, baseline audio replaced.

- [ ] **Step 8: Confirm approve audit trail**

```bash
python -c "
import json; from pathlib import Path
m = json.loads(Path('snapshots/phrase_guard/manifest.json').read_text())
print(len(m['approval_history']), 'approval record(s)')
print(m['approval_history'][0])
"
```
Expected: 1 approval record with run_id, previous_hash, new_hash, approved_at.

- [ ] **Step 9: Run full unit suite one final time**

```bash
pytest -v
```
Expected: all pass.

- [ ] **Step 10: Update PROGRESS.md**

Mark the CLI completion gate as verified. Add the run ID and observed exit codes. Note which browser you used to inspect the report.

- [ ] **Step 11: Commit**

```bash
git add cases/snapshots.yaml snapshots/ PROGRESS.md
git commit -m "feat: end-to-end verification gate passed"
```

---

### Task 13: GitHub Action (Gated — Complete Task 12 First)

**Files:**
- Create: `.github/workflows/snapshot.yml`
- Create: `README.md`

**Prerequisite:** Every checkbox in Task 12 must be checked before writing any YAML here.

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/snapshot.yml
name: TTS Snapshot CI

on:
  pull_request:
  workflow_dispatch:

jobs:
  snapshot-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install
        run: pip install -e .

      - name: Run snapshot check
        id: snap
        env:
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
        run: |
          snapshot check
          echo "exit_code=$?" >> "$GITHUB_OUTPUT"
        continue-on-error: true

      - name: Write job summary
        if: always()
        run: |
          EXIT=${{ steps.snap.outputs.exit_code }}
          if [ "$EXIT" = "0" ]; then STATE="PASS"; elif [ "$EXIT" = "1" ]; then STATE="REVIEW_REQUIRED"; else STATE="ERROR"; fi
          echo "## TTS Snapshot CI" >> "$GITHUB_STEP_SUMMARY"
          echo "**State: $STATE** (exit $EXIT)" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          echo "Download the report artifact to inspect audio and transcript comparisons." >> "$GITHUB_STEP_SUMMARY"

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: snapshot-report
          path: runs/*/report.html
          if-no-files-found: warn

      - name: Fail on ERROR or REVIEW_REQUIRED
        if: steps.snap.outputs.exit_code != '0'
        run: exit ${{ steps.snap.outputs.exit_code }}
```

- [ ] **Step 2: Write README.md** (keep it under 150 lines per spec)

```markdown
# TTS Snapshot CI

Catch review-worthy changes in ElevenLabs-rendered speech before they ship.

## What It Does

Text diffs show what changed. They do not show what a listener will hear.
TTS Snapshot CI generates candidate audio with ElevenLabs, compares it against
Git-tracked approved baselines, and produces a side-by-side listening report.

```
snapshot record   # generate initial baselines
snapshot check    # compare candidates; exit 0/1/2
snapshot approve  # promote candidates after listening
```

## The Three States

| State | Exit | Meaning |
|---|---:|---|
| `PASS` | 0 | No threshold crossed |
| `REVIEW_REQUIRED` | 1 | Listen before merging |
| `ERROR` | 2 | Comparison could not complete |

`REVIEW_REQUIRED` does not claim the TTS is defective. ElevenLabs STT errors
can appear as transcript differences. The report shows both transcripts beside
both audio players so you can assign cause.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
export ELEVENLABS_API_KEY=your_key
```

## Usage

Define cases in `cases/snapshots.yaml`, then:

```bash
snapshot record              # first time only
snapshot check               # on every change
snapshot approve <run-id> <case-id>...   # after listening to REVIEW_REQUIRED
```

The report is written to `runs/<run-id>/report.html`.

## Checks

Each case runs four comparisons:

1. **Transcript fidelity** — word-error rate vs expected text (ElevenLabs STT)
2. **Required phrases** — key terms must appear in the transcript
3. **Duration drift** — `max(baseline * pct, abs_floor_ms)` tolerance
4. **Leading / trailing silence drift** — independent edge measurements

Generation latency is reported but never gates results.

## GitHub Action

Add `ELEVENLABS_API_KEY` to repository secrets. The workflow runs on every PR,
uploads the HTML report as an artifact, and writes the named state to the job summary.

## Known Limitations

- ElevenLabs STT errors can appear as transcript regressions. Listen before assigning cause.
- Generated audio is not byte-deterministic. Hashes identify artifacts; they do not gate results.
- Thresholds are user-configured, not perceptually calibrated.
- Git-tracked baseline audio grows the repository. Keep the suite to 5–10 short clips.
- Silence and duration checks detect structural changes, not naturalness or prosody quality.
- Network load affects generation latency. Latency is informational only.
- 10-case test suite, one speaker, one accent. Routing accuracy on that set: see below.

## Routing Accuracy

[Fill in after running the 10-case verification set]

| Case | Expected | Actual | Match |
|---|---|---|---|
| ... | ... | ... | ... |

## Future Work

- Telegram / iOS Shortcut ingestion path
- PR comment with inline report summary
- Silence amplitude threshold exposed as a configurable YAML field
- Multi-speaker test cases
```

- [ ] **Step 3: Commit**

```bash
git add .github/ README.md
git commit -m "feat: GitHub Action wrapper and README"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|---|---|
| Python 3.11+, pydantic v2, typer | Task 1 |
| YAML cases with all fields | Task 1, 2 |
| `snapshot record` refuses existing baselines | Task 6, 7 |
| `snapshot check` never mutates baselines | Task 6, 8 |
| `snapshot approve` named case IDs, no approve-all | Task 10 |
| Transcript fidelity check | Task 3 |
| Required phrases check | Task 3 |
| Duration drift with max(pct, abs) | Task 3 |
| Leading/trailing silence drift (independent) | Task 3, 4 |
| Latency as metadata, never a gate | Tasks 5, 8, 11 |
| Audio hash as metadata, never a gate | Tasks 2, 6, 10 |
| Three states only: PASS / REVIEW_REQUIRED / ERROR | Task 2 |
| Exit codes 0 / 1 / 2 | Task 11 |
| Self-contained HTML report with audio players | Task 9 |
| Both transcripts + audio players per case row | Task 9 |
| STT limitation visible in report | Task 9 |
| Approved baseline + manifest in Git | Task 7 |
| Run artifacts git-ignored | Task 1 |
| Approval audit trail (hashes, timestamp, run ID) | Task 10 |
| ERROR candidate cannot be approved | Task 10 |
| Suite validation before paid API calls | Task 7, 8 |
| Secrets from env only | Task 11 |
| CLI completion gate verified live | Task 12 |
| GitHub Action only after gate | Task 13 |
| Action publishes named state in job summary | Task 13 |
| README with limitations and future work | Task 13 |

### Placeholder Scan

No TBD, TODO, or vague "add error handling" steps present.

### Type Consistency

- `audio_hash()` defined in `models.py`, used identically in `store.py`, `commands/record.py`, `commands/approve.py`.
- `AdapterProtocol` consumed in `commands/record.py` and `commands/check.py` with matching signatures.
- `ArtifactStore` constructor `(snapshots_dir, runs_dir)` consistent across all command files.
- `RunResult`, `CaseResult`, `BaselineManifest`, `ApprovalRecord` fields used consistently in tests and implementations.

