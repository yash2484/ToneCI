# 001: Product And Architecture

**Status:** Accepted  
**Date:** 2026-08-17

## Problem

Text diffs show what changed in a speech script, configuration, model, or voice selection. They do not show what a listener will hear. A plausible candidate can omit a phrase, change a pronunciation, gain dead air, or alter its pacing while passing ordinary code review.

TTS Snapshot CI gives teams a review workflow for rendered speech. It catches measurable changes and places the evidence needed for a listening decision in one report.

## Product Position

The tool is quality infrastructure for teams that generate speech. It extends prior voice-agent evaluation work from agent behavior and operational metrics into the rendered-speech layer.

The tool does not assign a universal audio quality score. Objective checks decide whether a person needs to review a change. The person decides whether to accept it.

## Architecture

The Python CLI is the application boundary. Commands orchestrate focused modules:

| Component | Responsibility |
|---|---|
| Configuration models | Parse and validate YAML cases and tolerances before paid API calls |
| ElevenLabs adapter | Generate speech and transcribe audio behind typed interfaces |
| Audio analyzer | Measure duration and leading/trailing silence |
| Comparison engine | Run pure comparisons and aggregate three-state results |
| Artifact store | Read approved snapshots and write isolated run artifacts |
| Report renderer | Build the listening report from structured results |
| CLI commands | Implement record, check, and named approval workflows |

The comparison engine does not depend on the ElevenLabs SDK. Adapter fakes can supply typed generation and transcription results in unit tests.

## Data Flow

### Record

1. Validate the complete suite.
2. Refuse cases that already have approved baselines.
3. Generate baseline audio through ElevenLabs TTS.
4. Transcribe and analyze the audio.
5. Write the audio and approved manifest.

### Check

1. Validate the complete suite before paid work.
2. Create a new immutable run directory.
3. Generate candidate audio for each case.
4. Transcribe and analyze baseline and candidate artifacts.
5. Run the four comparisons.
6. Aggregate case and run states.
7. Write structured results and an HTML report.
8. Exit with 0, 1, or 2 according to the named state.

`check` cannot update a baseline.

### Approve

1. Select a completed run and one or more explicit case IDs.
2. Reject errored or missing candidates.
3. Promote each selected candidate to the approved baseline.
4. Record prior/new hashes, approval time, and source run in the manifest.

There is no implicit approve-all operation and no forced record overwrite.

## Report Contract

Each case row contains:

- source text and expected transcript;
- baseline and candidate STT transcripts;
- highlighted transcript differences;
- required-phrase results;
- duration and silence measurements with configured tolerances;
- generation latency and file metadata;
- baseline and candidate audio players;
- the case state and reasons for review or error.

Showing transcripts beside the players lets a reviewer distinguish a likely STT error from an audible TTS change. The report must use only `PASS`, `REVIEW_REQUIRED`, or `ERROR` labels.

## Error Handling

- Invalid configuration fails before any paid API request.
- Missing credentials, unreadable files, unsupported audio, API failures, and incomplete analysis produce `ERROR`.
- The run keeps partial artifacts for diagnosis.
- Reruns create new run IDs and do not overwrite prior evidence.
- Secrets come from environment variables and never enter reports, manifests, logs, or Git.
- An errored candidate cannot be approved.

## GitHub Action Boundary

The local CLI is the product core. The GitHub Action is a thin adapter that:

1. invokes the same CLI;
2. uploads the generated report;
3. writes the named result state to the job summary.

Both `REVIEW_REQUIRED` and `ERROR` can make a check non-green, but the summary must preserve their distinct meanings. PR comments remain outside the MVP.

No Action YAML may be written until a live CLI run demonstrates `PASS`, `REVIEW_REQUIRED`, and `ERROR` with exit codes 0, 1, and 2.

## Alternatives Considered

### Metric-heavy audio similarity

Waveform or embedding similarity could produce one regression score. The MVP rejects this approach because audio distance does not establish perceptual degradation, and a weekend project cannot calibrate a defensible universal threshold.

### ElevenLabs model benchmark matrix

A matrix would compare voices, models, and settings. It helps model selection but does not protect an approved product behavior during code review.

### GitHub Action first

An Action makes adoption visible but adds workflow syntax, secrets, permissions, artifact, and remote-debugging failure modes. The project completes the CLI first and cuts the Action if time runs short.

## Verification

Unit tests cover pure comparison and lifecycle rules. Fakes exercise the ElevenLabs adapter boundary without claiming live integration success.

The CLI completion gate requires a live 5-10 case ElevenLabs run, browser inspection of the report, one demonstrated case in each state, and verified exit codes 0, 1, and 2. Only that evidence unlocks Action work.
