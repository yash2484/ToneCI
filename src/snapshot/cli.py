from __future__ import annotations
import os
from pathlib import Path
import typer
from dotenv import load_dotenv
from snapshot.models import RunState

app = typer.Typer(name="snapshot", help="TTS Snapshot CI — detect review-worthy speech changes.")

_DEFAULT_SUITE = Path("cases/snapshots.yaml")
_DEFAULT_SNAPSHOTS = Path("snapshots")
_DEFAULT_RUNS = Path("runs")
_DEFAULT_SITE_CONFIG = Path("site.yaml")
_DEFAULT_SITE_OUTPUT = Path("site")

load_dotenv()


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
    from snapshot.models import load_suite
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

    case_configs = {c.id: c for c in load_suite(suite).cases}
    html = render_report(result, baseline_audio, candidate_audio, case_configs)
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


@app.command()
def site(
    config: Path = typer.Option(_DEFAULT_SITE_CONFIG, "--config", "-c"),
    runs_dir: Path = typer.Option(_DEFAULT_RUNS, "--runs-dir"),
    output_dir: Path = typer.Option(_DEFAULT_SITE_OUTPUT, "--out"),
) -> None:
    """Build a curated static evidence site from completed run reports."""
    from snapshot.site import build_site

    try:
        build_site(config, runs_dir, output_dir)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(f"Site: {output_dir / 'index.html'}")


if __name__ == "__main__":
    app()
