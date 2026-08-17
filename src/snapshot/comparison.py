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
