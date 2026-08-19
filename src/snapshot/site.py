# src/snapshot/site.py
from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from snapshot.models import RunResult, RunState


class SiteRun(BaseModel):
    source: str
    note: str
    href: str | None = None
    screenshot: str | None = None


class SiteSection(BaseModel):
    title: str
    runs: list[SiteRun] = Field(min_length=1)


class SiteConfig(BaseModel):
    sections: list[SiteSection] = Field(min_length=1)

    @model_validator(mode="after")
    def no_duplicate_sources(self) -> "SiteConfig":
        sources = [run.source for section in self.sections for run in section.runs]
        if len(sources) != len(set(sources)):
            raise ValueError("Duplicate run source in site configuration")
        return self


class SiteEntry(BaseModel):
    source: str
    run_id: str
    state: RunState
    case_count: int
    note: str
    report_path: str
    detail_path: str | None = None
    href: str | None = None
    screenshot: str | None = None
    result: RunResult | None = None


_RUN_ID_RE = re.compile(r"(?:Run:\s*<code>|TTS Snapshot CI\s*[—-]\s*)([^<\s]+)")
_STATE_RE = re.compile(r'class="state-(PASS|REVIEW_REQUIRED|ERROR)"')


def _load_config(config_path: Path) -> SiteConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return SiteConfig.model_validate(raw)


def _entry_from_files(run: SiteRun, run_dir: Path) -> SiteEntry:
    report_path = run_dir / "report.html"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report.html for configured run {run.source!r}")

    results_path = run_dir / "results.json"
    if results_path.exists():
        result = RunResult.model_validate_json(results_path.read_text(encoding="utf-8"))
        return SiteEntry(
            source=run.source,
            run_id=result.run_id,
            state=result.state,
            case_count=len(result.cases),
            note=run.note,
            report_path=f"runs/{run.source}/report.html",
            detail_path=f"runs/{run.source}/index.html",
            href=run.href,
            screenshot=run.screenshot,
            result=result,
        )

    report = report_path.read_text(encoding="utf-8")
    run_match = _RUN_ID_RE.search(report)
    state_match = _STATE_RE.search(report)
    if not run_match or not state_match:
        raise ValueError(f"Could not read run metadata from {report_path}")
    case_count = len(re.findall(r"<td><code>[^<]+</code></td>", report))
    return SiteEntry(
        source=run.source,
        run_id=run_match.group(1),
        state=RunState(state_match.group(1)),
        case_count=case_count,
        note=run.note,
        report_path=f"runs/{run.source}/report.html",
        href=run.href,
        screenshot=run.screenshot,
    )


def _card(entry: SiteEntry) -> str:
    target = entry.href or entry.detail_path or entry.report_path
    external = entry.href is not None
    arrow = "↗" if external else ""
    screenshot = (
        f'<img class="run-card__shot" src="{escape(entry.screenshot)}" '
        f'alt="Screenshot of the GitHub check">' if entry.screenshot else ""
    )
    return """<article class="run-card">
  <div class="run-card__state state-{state}">{state}</div>
  <div class="run-card__body">
    <div class="run-card__meta">{run_id} · {case_count} case{plural}</div>
    <h3>{note}</h3>
    {screenshot}
    <a href="{target}"{rel}>{label} {arrow}</a>
  </div>
</article>""".format(
        state=entry.state.value,
        run_id=escape(entry.run_id),
        case_count=entry.case_count,
        plural="s" if entry.case_count != 1 else "",
        note=escape(entry.note),
        screenshot=screenshot,
        target=escape(target),
        rel=' target="_blank" rel="noopener"' if external else "",
        label="Open the pull request" if external else "View this check",
        arrow=arrow,
    )


def _render_index(config: SiteConfig, entries: dict[str, SiteEntry]) -> str:
    sections: list[str] = []
    for section in config.sections:
        cards = "".join(_card(entries[configured.source]) for configured in section.runs)
        sections.append(
            f'<section class="evidence-section"><h2>{escape(section.title)}</h2>'
            f'<div class="run-list">{cards}</div></section>'
        )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ToneCI / evidence</title>
<style>
  :root {
    color-scheme: light;
    --ink: #17202a;
    --muted: #66737f;
    --line: #d7dde2;
    --paper: #f7f8f6;
    --panel: #ffffff;
    --pass: #177245;
    --review: #9a5c00;
    --error: #c9372c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  main { max-width: 1080px; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
  .masthead { border-bottom: 2px solid var(--ink); padding-bottom: 1.25rem; }
  .eyebrow { color: var(--muted); font: 700 .72rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: .45rem 0 .7rem; font: 700 clamp(1.75rem, 4vw, 2.75rem)/1.05 Georgia, "Times New Roman", serif; letter-spacing: -.02em; }
  .lede { max-width: 700px; color: var(--muted); font-size: 1rem; line-height: 1.6; }
  .legend { display: flex; flex-wrap: wrap; gap: .75rem 1.25rem; margin-top: 1.2rem; color: var(--muted); font: .78rem ui-monospace, SFMono-Regular, Consolas, monospace; }
  .legend span::before { content: ""; display: inline-block; width: .6rem; height: .6rem; margin-right: .35rem; border-radius: 50%; background: currentColor; }
  .legend .pass { color: var(--pass); } .legend .review { color: var(--review); } .legend .error { color: var(--error); }
  .evidence-section { margin-top: 2.75rem; }
  h2 { margin: 0 0 1rem; font: 700 1.3rem/1.1 Georgia, "Times New Roman", serif; }
  .run-list { display: grid; gap: .75rem; }
  .run-card { display: grid; grid-template-columns: 11rem 1fr; background: var(--panel); border: 1px solid var(--line); }
  .run-card__state { display: grid; place-items: center; padding: 1rem; color: #fff; font: 800 .78rem ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .03em; }
  .state-PASS { background: var(--pass); } .state-REVIEW_REQUIRED { background: var(--review); } .state-ERROR { background: var(--error); }
  .run-card__body { padding: 1rem 1.1rem 1.05rem; }
  .run-card__meta { color: var(--muted); font: .73rem ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
  h3 { margin: .45rem 0 .6rem; font-size: 1rem; line-height: 1.35; }
  .run-card__shot { display: block; width: 100%; max-width: 560px; margin: .35rem 0 .6rem; border: 1px solid var(--line); }
  a { color: var(--ink); font-weight: 700; text-underline-offset: .18em; }
  a:hover { color: var(--pass); }
  .footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font: .78rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
  @media (max-width: 600px) { main { padding-top: 1.75rem; } .run-card { grid-template-columns: 1fr; } .run-card__state { justify-content: start; padding: .7rem 1rem; } }
</style>
</head>
<body>
<main>
  <header class="masthead">
    <div class="eyebrow">ToneCI · voice-change checks</div>
    <h1>Sound changed. Should someone listen?</h1>
    <p class="lede">ToneCI re-renders a script that was already approved and compares the new audio to the old. If the wording, timing, or pauses shifted beyond a set tolerance, it asks a human to listen. This page shows the checks that ran: green means nothing needed a second look, amber means it wanted one, red means the check could not finish.</p>
    <div class="legend" aria-label="Result states">
      <span class="pass">PASS</span><span class="review">REVIEW_REQUIRED</span><span class="error">ERROR</span>
    </div>
  </header>
  __SECTIONS__
  <footer class="footer">Amber asks for a human ear before approving. It is a request to review, not a verdict that the audio is broken.</footer>
</main>
</body>
</html>""".replace("__SECTIONS__", "".join(sections))


def _render_run_page(entry: SiteEntry) -> str:
    result = entry.result
    if result is None:
        raise ValueError(f"No result data for run {entry.source!r}")

    cards: list[str] = []
    for case in result.cases:
        reasons = "".join(
            f"<li><strong>{escape(r.check)}</strong>: {escape(r.detail)}</li>"
            for r in case.reasons
        ) or "<li>No issues flagged.</li>"
        cards.append(
            """<article class="case-card">
  <div class="case-card__head">
    <code>{case_id}</code>
    <span class="state-{state}">{state}</span>
  </div>
  <ul class="case-reasons">{reasons}</ul>
  <div class="case-meta">
    duration: {dur_base}ms &rarr; {dur_cand}ms<br>
    leading silence: {lead_base}ms &rarr; {lead_cand}ms<br>
    trailing silence: {trail_base}ms &rarr; {trail_cand}ms
  </div>
  <div class="case-transcripts">
    <div><strong>Before</strong><br>{base_tx}</div>
    <div><strong>After</strong><br>{cand_tx}</div>
  </div>
</article>""".format(
                case_id=escape(case.case_id),
                state=case.state.value,
                reasons=reasons,
                dur_base=case.baseline_duration_ms if case.baseline_duration_ms is not None else "?",
                dur_cand=case.candidate_duration_ms if case.candidate_duration_ms is not None else "?",
                lead_base=case.baseline_leading_silence_ms if case.baseline_leading_silence_ms is not None else "?",
                lead_cand=case.candidate_leading_silence_ms if case.candidate_leading_silence_ms is not None else "?",
                trail_base=case.baseline_trailing_silence_ms if case.baseline_trailing_silence_ms is not None else "?",
                trail_cand=case.candidate_trailing_silence_ms if case.candidate_trailing_silence_ms is not None else "?",
                base_tx=escape(case.baseline_transcript) if case.baseline_transcript else "—",
                cand_tx=escape(case.candidate_transcript) if case.candidate_transcript else "—",
            )
        )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__RUNID__ — ToneCI</title>
<style>
  :root {
    color-scheme: light;
    --ink: #17202a; --muted: #66737f; --line: #d7dde2; --paper: #f7f8f6; --panel: #ffffff;
    --pass: #177245; --review: #9a5c00; --error: #c9372c;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--paper); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  main { max-width: 900px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
  .back { display: inline-block; margin-bottom: 1.25rem; color: var(--muted); font-weight: 600; text-decoration: none; }
  .back:hover { color: var(--ink); }
  .masthead { border-bottom: 2px solid var(--ink); padding-bottom: 1.25rem; }
  .eyebrow { color: var(--muted); font: 700 .72rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: .5rem 0; font: 700 clamp(1.5rem, 3.5vw, 2.25rem)/1.05 Georgia, "Times New Roman", serif; }
  .run-meta { color: var(--muted); font: .78rem ui-monospace, SFMono-Regular, Consolas, monospace; }
  .note { margin: .9rem 0 0; font-size: 1rem; line-height: 1.5; }
  .case-list { display: grid; gap: 1rem; margin-top: 1.75rem; }
  .case-card { background: var(--panel); border: 1px solid var(--line); padding: 1rem 1.1rem; }
  .case-card__head { display: flex; justify-content: space-between; align-items: center; gap: .5rem; }
  .case-card__head code { font-weight: 700; }
  .case-card__head .state- { color: var(--muted); }
  .state-PASS { color: var(--pass); font-weight: 800; } .state-REVIEW_REQUIRED { color: var(--review); font-weight: 800; } .state-ERROR { color: var(--error); font-weight: 800; }
  .case-reasons { margin: .6rem 0; padding-left: 1.1rem; color: var(--review); font-size: .9rem; }
  .case-meta { color: var(--muted); font: .75rem/1.6 ui-monospace, SFMono-Regular, Consolas, monospace; }
  .case-transcripts { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top: .6rem; font-size: .9rem; }
  .case-transcripts div { border-top: 1px solid var(--line); padding-top: .4rem; }
  .full-report { display: inline-block; margin-top: 1.5rem; color: var(--ink); font-weight: 700; }
  @media (max-width: 600px) { .case-transcripts { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<main>
  <a class="back" href="../index.html">&larr; All checks</a>
  <header class="masthead">
    <div class="eyebrow">ToneCI / one check</div>
    <h1>__STATE__</h1>
    <p class="run-meta">__RUNID__ · __COUNT__ case__PLURAL__</p>
    <p class="note">__NOTE__</p>
  </header>
  <section class="case-list">__CARDS__</section>
  <a class="full-report" href="report.html">Full report with audio &rarr;</a>
</main>
</body>
</html>""".replace("__STATE__", escape(entry.state.value)).replace(
        "__RUNID__", escape(entry.run_id)
    ).replace(
        "__COUNT__", str(entry.case_count)
    ).replace(
        "__PLURAL__", "s" if entry.case_count != 1 else ""
    ).replace(
        "__NOTE__", escape(entry.note)
    ).replace("__CARDS__", "".join(cards))


def build_site(config_path: Path, runs_dir: Path, output_dir: Path) -> None:
    config = _load_config(config_path)
    entries: dict[str, SiteEntry] = {}
    for section in config.sections:
        for configured in section.runs:
            entry = _entry_from_files(configured, runs_dir / configured.source)
            entries[configured.source] = entry

    output_dir.mkdir(parents=True, exist_ok=True)
    for configured in [run for section in config.sections for run in section.runs]:
        source_dir = runs_dir / configured.source
        target_dir = output_dir / "runs" / configured.source
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_dir / "report.html", target_dir / "report.html")

    for entry in entries.values():
        if entry.result is not None:
            target_dir = output_dir / "runs" / entry.source
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "index.html").write_text(_render_run_page(entry), encoding="utf-8")

    (output_dir / "index.html").write_text(_render_index(config, entries), encoding="utf-8")