# 002: Snapshot Contract

**Status:** Accepted  
**Date:** 2026-08-17

## Canonical Terms

- **Test case:** A versioned specification of source text, expected transcript, required phrases, generation settings, and comparison tolerances.
- **Approved baseline:** Git-tracked audio and metadata that a person has accepted as the reference for one test case.
- **Candidate:** Audio generated during one check run for comparison with an approved baseline.
- **Run:** An immutable set of candidates, measurements, results, and a report created by one `check` invocation.
- **Review threshold:** A configured boundary that requests human inspection. Crossing it does not prove a defect.
- **Approval:** An explicit promotion of named candidates from a completed run into approved baselines.

## Result States

The system exposes exactly three states:

| State | Rule |
|---|---|
| `PASS` | A valid comparison completed and no review threshold crossed |
| `REVIEW_REQUIRED` | A valid comparison completed and one or more review thresholds crossed |
| `ERROR` | The system could not complete a valid comparison |

Aggregation uses `ERROR > REVIEW_REQUIRED > PASS`. The design excludes `FAIL`, `WARN`, and numeric quality grades.

## Test Case Inputs

Each case defines:

- a stable case ID;
- source text sent to TTS;
- expected spoken transcript;
- zero or more required phrases;
- ElevenLabs voice, model, and supported generation settings;
- a transcript-fidelity threshold;
- duration percentage and absolute-millisecond tolerances;
- leading and trailing silence tolerances.

The implementation validates the entire suite before starting generation.

## Objective Comparisons

### Transcript Fidelity

ElevenLabs STT transcribes baseline and candidate audio. The comparison normalizes case, spacing, and punctuation, then measures each transcript against expected text. Crossing the configured word-error threshold produces `REVIEW_REQUIRED`.

The result identifies an observed transcript mismatch, not a proven TTS failure. The report shows expected text, both STT transcripts, transcript differences, and both audio clips so a person can assign cause.

### Required Phrases

The tool checks normalized required phrases in the STT transcript. Missing product names, numbers, URLs, warnings, or other specified wording produces `REVIEW_REQUIRED`.

Required-phrase matching follows the same documented normalization as transcript fidelity. It does not use fuzzy semantic matching in the MVP.

### Duration Drift

The allowed candidate-to-baseline duration delta is:

```text
max(baseline duration * configured percentage, configured absolute milliseconds)
```

The more permissive tolerance prevents short clips from tripping on small fixed changes and long clips from tripping on an overly narrow millisecond floor. Exceeding the resolved tolerance produces `REVIEW_REQUIRED`.

### Leading And Trailing Silence Drift

The analyzer measures leading and trailing silence independently for baseline and candidate audio. Each edge has an explicit millisecond tolerance. Exceeding either tolerance produces `REVIEW_REQUIRED` even when total duration remains stable.

The implementation must document its silence amplitude threshold and minimum window so measurements remain reproducible.

## Informational Metadata

The report includes:

- TTS generation latency;
- baseline and candidate file sizes;
- audio duration;
- audio hashes;
- SDK, model, voice, and generation identifiers available from the provider.

Latency deltas may receive visual emphasis but cannot alter state or exit code because network and provider load affect them.

Audio hashes identify the exact artifacts under review. They do not gate results because generated audio need not be byte-deterministic.

## Baseline Lifecycle

### Initial Recording

`snapshot record` writes only missing baselines. It refuses to replace an approved baseline.

### Comparison

`snapshot check` writes candidates and run artifacts. It never changes an approved baseline.

### Replacement

`snapshot approve <case-id>...` is the only sanctioned replacement path. A reviewer listens to the candidate, names each approved case, and promotes it from a completed run. The manifest records:

- source run ID;
- approval timestamp;
- previous artifact hash;
- new artifact hash;
- applicable case and generation metadata.

The command rejects `ERROR` candidates. It accepts `REVIEW_REQUIRED` candidates after explicit human selection.

There is no `record --force` and no implicit approve-all. Deleting or replacing baseline files by hand is unsupported because it creates an audit gap.

## Artifact Ownership

Approved baseline audio and manifests are committed to Git. This makes comparisons reproducible and baseline changes visible in code review. The MVP limits the suite to 5-10 short clips to constrain repository growth.

Candidate audio, results, and reports live under a run ID and remain untracked. A run never overwrites another run.

## Exit And CI Semantics

The CLI exits with:

- `0` for `PASS`;
- `1` for `REVIEW_REQUIRED`;
- `2` for `ERROR`.

CI systems may treat both nonzero values alike. The Action must display the named state and reasons in the job summary and upload the report. Consumers must not infer the distinction from check color or exit code alone.

## Invariants

- The public result vocabulary contains exactly three states.
- No valid `check` mutates approved artifacts.
- Every approved replacement names one or more cases and records its source run.
- Every threshold crossing requests review without asserting perceptual failure.
- STT-derived checks remain inspectable beside source audio.
- Latency and hashes remain metadata rather than gates.
- Action work cannot begin before the CLI completion gate passes.
