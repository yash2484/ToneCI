from pathlib import Path

import pytest

from snapshot.site import build_site


def _write_report(run_dir: Path, run_id: str, state: str) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "report.html").write_text(
        f'<title>TTS Snapshot CI — {run_id}</title>'
        f'<p>State: <span class="state-{state}">{state}</span></p>',
        encoding="utf-8",
    )


def test_build_site_renders_configured_sections_and_copies_reports(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "site"
    _write_report(runs_dir / "pass-run", "20260818T122142Z-441fe4", "PASS")
    _write_report(runs_dir / "ci-run", "20260818T141700Z-ci1234", "REVIEW_REQUIRED")
    (runs_dir / "pass-run" / "results.json").write_text(
        '{"run_id":"20260818T122142Z-441fe4","state":"PASS","cases":[]}',
        encoding="utf-8",
    )
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: Calibration runs
    runs:
      - source: pass-run
        note: Six-case suite passes.
  - title: Verify it in CI
    runs:
      - source: ci-run
        note: Pull request review gate.
""",
        encoding="utf-8",
    )

    build_site(config, runs_dir, output_dir)

    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Calibration runs" in index
    assert "Verify it in CI" in index
    assert "Six-case suite passes." in index
    assert "20260818T122142Z-441fe4" in index
    assert "state-PASS" in index
    assert "state-REVIEW_REQUIRED" in index
    assert (output_dir / "runs/pass-run/report.html").exists()
    assert (output_dir / "runs/ci-run/report.html").exists()


def test_build_site_rejects_missing_configured_run(tmp_path: Path) -> None:
    config = tmp_path / "site.yaml"
    config.write_text(
        """sections:
  - title: Calibration runs
    runs:
      - source: missing-run
        note: This must fail loudly.
""",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing-run"):
        build_site(config, tmp_path / "runs", tmp_path / "site")
