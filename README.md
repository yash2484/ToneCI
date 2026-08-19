# ToneCI

> An opinionated tts-slop-checker for ElevenLabs-rendered speech.

ToneCI catches review-worthy changes in rendered speech before they ship. It records approved audio baselines, generates candidates from the same YAML suite, measures the differences, and writes a side-by-side HTML report for a human to review.

It does not pretend to calculate a universal speech-quality score. It flags measurable changes, then gives the reviewer the audio and evidence needed to make the call.

## What it checks

- Transcript fidelity with ElevenLabs Speech-to-Text
- Required phrases that must remain observable
- Playback-duration drift
- Leading and trailing silence drift

Each run has one result state:

| State | Exit code | Meaning |
| --- | ---: | --- |
| `PASS` | `0` | Comparison completed without crossing a review threshold. |
| `REVIEW_REQUIRED` | `1` | A valid comparison completed, but a threshold requests human review. |
| `ERROR` | `2` | The tool could not complete a valid comparison. |

`REVIEW_REQUIRED` is not a quality verdict. Speech-to-text observations can differ from what a listener hears, so review the report before approving a candidate.

## Requirements

- Python 3.11 or later
- FFmpeg and FFprobe on `PATH`
- An ElevenLabs API key with Text-to-Speech and Speech-to-Text permissions

The example suite uses George (`JBFqnCBsd6RMkjVDRZzb`), a premade voice verified with a Free-tier ElevenLabs account. Your account's available voices can differ.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project and development dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create a `.env` file in the repository root:

```dotenv
ELEVENLABS_API_KEY=your_api_key_here
```

The `.env` file is ignored by Git and loaded by the CLI.

Install FFmpeg on Windows with WinGet:

```powershell
winget install --id Gyan.FFmpeg -e
```

Restart your terminal after installation, then verify both commands resolve:

```powershell
ffmpeg -version
ffprobe -version
```

## Quick start

Record a baseline for any case without one:

```powershell
snapshot record
```

Generate candidates, compare them to approved baselines, and write a report:

```powershell
snapshot check
```

The command prints a run ID and report path. Open the report in a browser to compare baseline and candidate audio, transcripts, measurements, and review reasons:

```text
runs/<run-id>/report.html
```

After listening to the report, promote only the named candidates you approve:

```powershell
snapshot approve <run-id> hello_world
```

Approval replaces the selected baseline and records the previous and new audio hashes in the baseline manifest.

## How it was verified

The three result states were demonstrated against a live Free-tier ElevenLabs account with the George voice:

| State | Exit code | Run |
| --- | ---: | --- |
| `PASS` — full six-case suite | `0` | `20260818T122142Z-441fe4` |
| `REVIEW_REQUIRED` — induced required-phrase crossing | `1` | `20260818T122533Z-98ebf7` |
| `ERROR` — missing baseline and invalid voice | `2` | `20260818T122615Z-0a3f8a`, `20260818T122633Z-ef2b85` |

Each run wrote a side-by-side HTML report with baseline and candidate audio players, transcripts with highlighted differences, measurements, and review reasons. A named approval from the `PASS` run recorded a full audit trail in the manifest: previous hash, new hash, source run ID, and timestamp. The 61-test regression suite covers the comparison engine, audio measurement, artifact store, report renderer, static site builder, and CLI lifecycle with deterministic fake adapters.

## GitHub Actions

A workflow in [`.github/workflows/snapshot.yml`](.github/workflows/snapshot.yml) runs `snapshot check` on every pull request, uploads the report as a build artifact, and writes the named result state to the job summary. `REVIEW_REQUIRED` and `ERROR` fail the check with distinct exit codes while keeping their meanings visible by name.

### Live evidence site

[`snapshot site`](src/snapshot/site.py) builds a curated static index of completed runs from [`site.yaml`](site.yaml), copies the selected reports, and writes them under `site/`. A deployment workflow in [`.github/workflows/pages.yml`](.github/workflows/pages.yml) publishes that directory to GitHub Pages:

- Live site: <https://yash2484.github.io/ToneCI/>

Rebuild locally whenever you want to include a new run:

```powershell
snapshot site
```

Add a run to the curated list by giving its `runs/` directory name in `site.yaml`. The command fails loudly if a listed run is missing or duplicated, and the generated `site/` directory is committed so the published page always matches the repo.

## Test cases

Define cases in [`cases/snapshots.yaml`](cases/snapshots.yaml):

```yaml
cases:
  - id: hello_world
    source_text: "Hello world. This is a test."
    expected_transcript: "Hello world. This is a test."
    required_phrases:
      - "Hello world"
    voice_id: "JBFqnCBsd6RMkjVDRZzb"
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"
    tolerances:
      transcript_wer_threshold: 0.15
      duration_pct: 0.10
      duration_abs_ms: 200
      leading_silence_ms: 150
      trailing_silence_ms: 150
```

Approved audio and manifests live under `snapshots/<case-id>/` and belong in Git. Generated `runs/` artifacts remain local and are ignored.

## Development

Run the regression suite:

```powershell
.venv\Scripts\pytest.exe -q
```

The suite includes deterministic fake-adapter tests. A live run requires an ElevenLabs key, a voice available to that key, and FFmpeg for MP3 measurement.

## Limitations

- ElevenLabs Speech-to-Text is measurement evidence, not ground truth about audio content.
- Speech-to-Text digit normalization is nondeterministic: the same sentence can transcribe as words one run and as numerals the next. Cases that depend on exact digit strings flag on STT variance rather than TTS regressions, so the committed suite keeps digit-heavy content out of required phrases.
- Generated audio can vary between identical requests, so audio hashes identify artifacts but never determine pass/fail status.
- Thresholds request review; they do not measure naturalness, emotion, prosody, or universal speech quality.
- Generation latency depends on the provider and network, so it is reported as metadata rather than a gate.
