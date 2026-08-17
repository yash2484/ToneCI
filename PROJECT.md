# TTS Snapshot CI

## Purpose

TTS Snapshot CI catches review-worthy changes in rendered speech before a team ships them. It generates candidate speech with ElevenLabs, compares it with approved audio snapshots, and produces a side-by-side listening report for human review.

The project extends prior work evaluating voice-agent quality, behavior, latency, and reliability. It focuses on the speech layer: whether a text, voice, model, or settings change altered what a listener hears.

## Product Contract

For a fixed test case, the tool compares candidate speech with a Git-tracked approved baseline and returns exactly one run state:

- `PASS`: generation and comparison succeeded without crossing a review threshold.
- `REVIEW_REQUIRED`: at least one objective comparison crossed a configured threshold and a person must inspect the result.
- `ERROR`: configuration, generation, transcription, file, or analysis failure prevented a valid comparison.

`REVIEW_REQUIRED` does not claim that the TTS output is defective. ElevenLabs STT is a measurement dependency and can mishear valid speech. The report exposes both transcripts and both audio clips so a reviewer can resolve that ambiguity.

## Weekend MVP

### In Scope

- Python 3.11+ CLI.
- YAML test cases for source text, expected transcript, required phrases, ElevenLabs voice/model/settings, and comparison tolerances.
- ElevenLabs Text-to-Speech candidate generation.
- ElevenLabs Speech-to-Text fidelity measurement.
- Git-tracked baseline audio and manifests.
- Four objective comparisons:
  - transcript fidelity;
  - required phrases;
  - duration drift;
  - leading and trailing silence drift.
- A self-contained or portable HTML report with baseline and candidate audio players, transcripts, highlighted differences, and measurements.
- Explicit baseline recording and named candidate approval.
- Generation latency, file size, and audio duration as reported metadata.
- A thin GitHub Action wrapper only after the CLI passes its end-to-end verification gate.

### Out of Scope

- A single perceptual-quality or audio-similarity score.
- Claims that objective checks prove speech quality.
- Automatic baseline updates or implicit approve-all behavior.
- Latency as a build-failing gate.
- External baseline storage.
- A hosted service, web application, database, or multi-user system.
- Full voice-agent, RAG, call-routing, or conversational-agent evaluation.
- PR comments in the weekend MVP. The Action may upload the report and write a job summary.

## Commands

- `snapshot record`: generate missing initial baselines. Refuse to overwrite an existing baseline.
- `snapshot check`: generate candidates, run comparisons, and write a report without changing approved artifacts.
- `snapshot approve <case-id>...`: promote named candidates from a completed run and record approval history.

Intentional text, voice, model, or settings changes still use `check -> listen -> approve`. There is no `record --force`. Manual baseline replacement is unsupported because it breaks the approval trail.

## Exit Codes

| State | Exit code | Meaning |
|---|---:|---|
| `PASS` | 0 | Valid comparison; no review threshold crossed |
| `REVIEW_REQUIRED` | 1 | Valid comparison; human review required |
| `ERROR` | 2 | A valid comparison could not complete |

The GitHub Action must publish the state by name in its job summary. It must not rely on consumers inferring state from a nonzero exit code.

## Artifact Layout

```text
PROJECT.md
PROGRESS.md
design/
  001-product-and-architecture.md
  002-snapshot-contract.md
cases/
  snapshots.yaml
snapshots/
  <case-id>/
    baseline.mp3
    manifest.json
runs/
  <run-id>/
    candidates/<case-id>.mp3
    results.json
    report.html
src/
tests/
```

Approved baseline audio and manifests belong in Git. Generated run artifacts stay local and must be ignored by Git.

## Build Order

1. Define typed configuration and result models.
2. Implement pure comparison functions with tests.
3. Implement audio analysis and local fixtures.
4. Add typed ElevenLabs TTS and STT adapters.
5. Implement `record`, then `check`, then named `approve`.
6. Generate and inspect the side-by-side HTML report.
7. Verify a real 5-10 case ElevenLabs suite with all three states and exit codes.
8. Only after step 7 passes, add the thin GitHub Action wrapper.

## CLI Completion Gate

The CLI is complete only after a real ElevenLabs run demonstrates:

- at least one `PASS` case;
- at least one induced `REVIEW_REQUIRED` case;
- at least one controlled `ERROR` case;
- exit codes 0, 1, and 2;
- a browser-inspected report containing source text, expected text, baseline transcript, candidate transcript, highlighted differences, measurements, and both audio players.

Fake-adapter tests do not satisfy this gate.

## Cut Order

If the weekend schedule slips, cut work in this order:

1. PR comment integration.
2. The GitHub Action wrapper.
3. Cosmetic report polish.

Do not cut the working CLI, side-by-side report, four comparisons, explicit approval lifecycle, or documented STT limitation.

## Known Limitations

- ElevenLabs STT errors can appear as TTS fidelity regressions. A human must listen before assigning cause.
- Generated audio need not be byte-deterministic. Hashes identify compared artifacts but do not gate results.
- Thresholds are configured by the user and are not perceptually calibrated.
- Git-tracked audio increases repository size. The MVP keeps the suite to 5-10 short clips.
- Silence and duration checks detect structural changes but do not measure naturalness, emotion, or prosody quality.
- Network and provider load affect generation latency, so latency remains informational.

## Success Criteria

- A reviewer can install the CLI, record a baseline, introduce a speech-affecting change, run a check, and resolve the result from one report.
- Every result uses one of the three documented states.
- Normal checks cannot mutate approved baselines.
- A reviewer can trace each approved baseline replacement through old/new hashes and approval metadata.
- The README and application narrative report limitations without presenting review thresholds as ground-truth quality judgments.

## Historical Context

`VoiceRouter_Project_Spec.md` describes an earlier voice-to-CRM concept. It remains in the repository as historical context. This file defines the active project scope.
