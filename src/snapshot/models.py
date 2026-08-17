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

    def __init__(
        self,
        transcript_wer_threshold: float = 0.0,
        duration_pct: float = 0.0,
        duration_abs_ms: int = 0,
        leading_silence_ms: int = 0,
        trailing_silence_ms: int = 0,
        **data: Any,
    ) -> None:
        super().__init__(
            transcript_wer_threshold=transcript_wer_threshold,
            duration_pct=duration_pct,
            duration_abs_ms=duration_abs_ms,
            leading_silence_ms=leading_silence_ms,
            trailing_silence_ms=trailing_silence_ms,
            **data,
        )


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
