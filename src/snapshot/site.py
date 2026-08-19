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


_RUN_ID_RE = re.compile(r"(?:Run:\s*<code>|TTS Snapshot CI\s*[—-]\s*)([^<\s]+)")
_STATE_RE = re.compile(r'class="state-(PASS|REVIEW_REQUIRED|ERROR)"')


def _load_config(config_path: Path) -> SiteConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return SiteConfig.model_validate(raw)


def _entry_from_files(source: str, note: str, run_dir: Path) -> SiteEntry:
    report_path = run_dir / "report.html"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report.html for configured run {source!r}")

    results_path = run_dir / "results.json"
    if results_path.exists():
        result = RunResult.model_validate_json(results_path.read_text(encoding="utf-8"))
        return SiteEntry(
            source=source,
            run_id=result.run_id,
            state=result.state,
            case_count=len(result.cases),
            note=note,
            report_path=f"runs/{source}/report.html",
        )

    report = report_path.read_text(encoding="utf-8")
    run_match = _RUN_ID_RE.search(report)
    state_match = _STATE_RE.search(report)
    if not run_match or not state_match:
        raise ValueError(f"Could not read run metadata from {report_path}")
    case_count = len(re.findall(r'<td><code>[^<]+</code></td>', report))
    return SiteEntry(
        source=source,
        run_id=run_match.group(1),
        state=RunState(state_match.group(1)),
        case_count=case_count,
        note=note,
        report_path=f"runs/{source}/report.html",
    )


def _render_index(config: SiteConfig, entries: dict[str, SiteEntry]) -> str:
    sections: list[str] = []
    for section in config.sections:
        rows: list[str] = []
        for configured in section.runs:
            entry = entries[configured.source]
            rows.append(
                """<article class="run-card">
  <div class="run-card__state state-{state}">{state}</div>
  <div class="run-card__body">
    <div class="run-card__meta">{run_id} · {case_count} case{plural}</div>
    <h3>{note}</h3>
    <a href="{report_path}">Open report <span aria-hidden="true">↗</span></a>
  </div>
</article>""".format(
                    state=entry.state.value,
                    run_id=escape(entry.run_id),
                    case_count=entry.case_count,
                    plural="s" if entry.case_count != 1 else "",
                    note=escape(entry.note),
                    report_path=escape(entry.report_path),
                )
            )
        sections.append(
            f'<section class="evidence-section"><h2>{escape(section.title)}</h2>'
            f'<div class="run-list">{"".join(rows)}</div></section>'
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
  main { max-width: 1080px; margin: 0 auto; padding: 3.5rem 1.25rem 5rem; }
  .masthead { border-bottom: 2px solid var(--ink); padding-bottom: 1.5rem; }
  .eyebrow { color: var(--muted); font: 700 .72rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: .55rem 0 .8rem; font: 700 clamp(2.4rem, 7vw, 5.5rem)/.92 Georgia, "Times New Roman", serif; letter-spacing: -.04em; }
  .lede { max-width: 700px; color: var(--muted); font-size: 1.05rem; line-height: 1.6; }
  .legend { display: flex; flex-wrap: wrap; gap: .75rem 1.25rem; margin-top: 1.4rem; color: var(--muted); font: .78rem ui-monospace, SFMono-Regular, Consolas, monospace; }
  .legend span::before { content: ""; display: inline-block; width: .6rem; height: .6rem; margin-right: .35rem; border-radius: 50%; background: currentColor; }
  .legend .pass { color: var(--pass); } .legend .review { color: var(--review); } .legend .error { color: var(--error); }
  .evidence-section { margin-top: 3rem; }
  h2 { margin: 0 0 1rem; font: 700 1.35rem/1.1 Georgia, "Times New Roman", serif; }
  .run-list { display: grid; gap: .75rem; }
  .run-card { display: grid; grid-template-columns: 11rem 1fr; background: var(--panel); border: 1px solid var(--line); }
  .run-card__state { display: grid; place-items: center; padding: 1rem; color: #fff; font: 800 .78rem ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .03em; }
  .state-PASS { background: var(--pass); } .state-REVIEW_REQUIRED { background: var(--review); } .state-ERROR { background: var(--error); }
  .run-card__body { padding: 1rem 1.1rem 1.05rem; }
  .run-card__meta { color: var(--muted); font: .73rem ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
  h3 { margin: .45rem 0 .65rem; font-size: 1rem; line-height: 1.35; }
  a { color: var(--ink); font-weight: 700; text-underline-offset: .18em; }
  a:hover { color: var(--pass); }
  .footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font: .78rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
  @media (max-width: 600px) { main { padding-top: 2rem; } .run-card { grid-template-columns: 1fr; } .run-card__state { justify-content: start; padding: .7rem 1rem; } }
</style>
</head>
<body>
<main>
  <header class="masthead">
    <div class="eyebrow">ToneCI / rendered speech evidence</div>
    <h1>Does the voice change hold up?</h1>
    <p class="lede">A small, inspectable history of ElevenLabs snapshot checks. Each entry opens the original report with audio, transcripts, measurements, and the reason a human reviewer was or was not needed.</p>
    <div class="legend" aria-label="Result states">
      <span class="pass">PASS</span><span class="review">REVIEW_REQUIRED</span><span class="error">ERROR</span>
    </div>
  </header>
  __SECTIONS__
  <footer class="footer">REVIEW_REQUIRED requests inspection. It does not assert a TTS defect. Listen to both clips before assigning cause.</footer>
</main>
</body>
</html>""".replace("__SECTIONS__", "".join(sections))


def build_site(config_path: Path, runs_dir: Path, output_dir: Path) -> None:
    config = _load_config(config_path)
    entries: dict[str, SiteEntry] = {}
    for section in config.sections:
        for configured in section.runs:
            entry = _entry_from_files(configured.source, configured.note, runs_dir / configured.source)
            entries[configured.source] = entry

    output_dir.mkdir(parents=True, exist_ok=True)
    for configured in [run for section in config.sections for run in section.runs]:
        source_dir = runs_dir / configured.source
        target_dir = output_dir / "runs" / configured.source
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_dir / "report.html", target_dir / "report.html")
    (output_dir / "index.html").write_text(_render_index(config, entries), encoding="utf-8")
