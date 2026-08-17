# TTS Snapshot CI

TTS Snapshot CI catches review-worthy changes in ElevenLabs-rendered speech before they ship. It records approved audio baselines, generates candidates from the same YAML suite, measures changes, and writes a side-by-side HTML report for human review.

The tool does not claim to score speech quality. It flags measurable changes and gives a reviewer the evidence needed to listen and decide.

## What It Checks

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

## Quick Start

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

## Test Cases

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
- Generated audio can vary between identical requests, so audio hashes identify artifacts but never determine pass/fail status.
- Thresholds request review; they do not measure naturalness, emotion, prosody, or universal speech quality.
- Generation latency depends on the provider and network, so it is reported as metadata rather than a gate.
