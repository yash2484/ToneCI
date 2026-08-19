from pathlib import Path

import pytest

from snapshot.site import build_site


def _write_report(run_dir: Path, run_id: str, state: str) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "report.html").write_text(
        f'<title>TTS Snapshot CI — {run_id}</title>'
        f'<p>Run: <code>{run_id}</code></p>'
        f'<p>State: <span class="state-{state}">{state}</span></p>',
        encoding="utf-8",
    )


def _write_results(run_dir: Path, run_id: str, state: str, cases: list[dict]) -> None:
    import json

    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "state": state, "cases": cases}
    (run_dir / "results.json").write_text(json.dumps(payload), encoding="utf-8")


def test_build_site_renders_sections_scoped_pages_and_friendly_copy(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "site"
    _write_report(runs_dir / "pass-run", "20260818T122142Z-441fe4", "PASS")
    _write_results(
        runs_dir / "pass-run",
        "20260818T122142Z-441fe4",
        "PASS",
        [
            {
                "case_id": "hello_world",
                "state": "PASS",
                "baseline_transcript": "Hello world.",
                "candidate_transcript": "Hello world.",
            }
        ],
    )
    _write_report(runs_dir / "ci-run", "20260818T141700Z-ci1234", "REVIEW_REQUIRED")
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: Checks I ran while building it
    runs:
      - source: pass-run
        note: Six-case suite passes.
  - title: The same check, running in GitHub Actions
    runs:
      - source: ci-run
        note: A pull request review gate.
""",
        encoding="utf-8",
    )

    build_site(config, runs_dir, output_dir)

    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Sound changed. Should someone listen?" in index
    assert "Checks I ran while building it" in index
    assert "The same check, running in GitHub Actions" in index
    assert "state-PASS" in index
    assert "state-REVIEW_REQUIRED" in index
    assert 'href="runs/pass-run/index.html"' in index
    assert 'href="runs/ci-run/report.html"' in index
    assert (output_dir / "runs/pass-run/report.html").exists()
    assert (output_dir / "runs/ci-run/report.html").exists()

    scoped = (output_dir / "runs/pass-run/index.html").read_text(encoding="utf-8")
    assert "20260818T122142Z-441fe4" in scoped
    assert "hello_world" in scoped
    assert 'href="report.html"' in scoped


def test_scoped_page_lists_per_case_reasons(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "site"
    _write_report(runs_dir / "flagged-run", "20260818T121139Z-67659e", "REVIEW_REQUIRED")
    _write_results(
        runs_dir / "flagged-run",
        "20260818T121139Z-67659e",
        "REVIEW_REQUIRED",
        [
            {
                "case_id": "phone_number",
                "state": "REVIEW_REQUIRED",
                "reasons": [
                    {
                        "check": "transcript_fidelity",
                        "detail": "Word error rate 0.33 exceeds threshold 0.15",
                    }
                ],
            }
        ],
    )
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: Checks I ran while building it
    runs:
      - source: flagged-run
        note: Phone number transcription flaked.
""",
        encoding="utf-8",
    )

    build_site(config, runs_dir, output_dir)

    scoped = (output_dir / "runs/flagged-run/index.html").read_text(encoding="utf-8")
    assert "phone_number" in scoped
    assert "transcript_fidelity" in scoped
    assert "Word error rate 0.33 exceeds threshold 0.15" in scoped
    assert "REVIEW_REQUIRED" in scoped


def test_build_site_supports_external_href_and_screenshot(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "site"
    _write_report(runs_dir / "ci-run", "20260818T141700Z-ci1234", "ERROR")
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: The same check, running in GitHub Actions
    runs:
      - source: ci-run
        note: A pull request with a missing baseline.
        href: https://github.com/yash2484/ToneCI/pull/2
        screenshot: images/pr2-check.png
""",
        encoding="utf-8",
    )

    build_site(config, runs_dir, output_dir)

    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="https://github.com/yash2484/ToneCI/pull/2"' in index
    assert 'src="images/pr2-check.png"' in index
    assert 'href="runs/ci-run/index.html"' not in index


def test_build_site_rejects_missing_configured_run(tmp_path: Path) -> None:
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: Checks I ran while building it
    runs:
      - source: missing-run
        note: This must fail loudly.
""",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing-run"):
        build_site(config, tmp_path / "runs", tmp_path / "site")