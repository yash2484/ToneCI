# src/snapshot/renderer.py
from __future__ import annotations
import base64
from html import escape
from diff_match_patch import diff_match_patch
from jinja2 import Environment, BaseLoader
from snapshot.models import RunResult

_DIFF_INSERT = 1
_DIFF_DELETE = -1


def transcript_diff_pair(reference: str, hypothesis: str) -> tuple[str, str]:
    """Return (baseline_html, candidate_html) with deletions/insertions highlighted.

    Deletions mark words present in the baseline but missing from the candidate.
    Insertions mark words added in the candidate. Equal text renders plain.
    """
    if reference == hypothesis:
        return escape(reference), escape(hypothesis)
    dmp = diff_match_patch()
    diffs = dmp.diff_main(reference, hypothesis)
    dmp.diff_cleanupSemantic(diffs)
    base_parts: list[str] = []
    cand_parts: list[str] = []
    for op, text in diffs:
        esc = escape(text)
        if op == _DIFF_INSERT:
            cand_parts.append(f'<ins class="diff-ins">{esc}</ins>')
        elif op == _DIFF_DELETE:
            base_parts.append(f'<del class="diff-del">{esc}</del>')
        else:
            base_parts.append(esc)
            cand_parts.append(esc)
    return "".join(base_parts), "".join(cand_parts)

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TTS Snapshot CI — {{ result.run_id }}</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.4rem; }
  .state-PASS { color: #1a7f37; font-weight: bold; }
  .state-REVIEW_REQUIRED { color: #9a5c00; font-weight: bold; }
  .state-ERROR { color: #cf222e; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
  th, td { padding: 0.5rem 0.75rem; border: 1px solid #d0d7de; text-align: left; vertical-align: top; }
  th { background: #f6f8fa; }
  audio { width: 100%; max-width: 320px; }
  .reasons { color: #9a5c00; font-size: 0.85rem; }
  .meta { font-size: 0.8rem; color: #57606a; }
  details summary { cursor: pointer; font-size: 0.85rem; color: #0969da; }
  .diff-ins { background: #ccffd8; color: #1a7f37; }
  .diff-del { background: #ffecec; color: #cf222e; text-decoration: line-through; }
</style>
</head>
<body>
<h1>TTS Snapshot CI</h1>
<p>Run: <code>{{ result.run_id }}</code> &nbsp;|&nbsp;
   State: <span class="state-{{ result.state.value }}">{{ result.state.value }}</span></p>

<table>
<thead>
<tr>
  <th>Case</th><th>State</th><th>Source / Expected</th>
  <th>Baseline transcript</th><th>Candidate transcript</th>
  <th>Baseline audio</th><th>Candidate audio</th>
  <th>Measurements</th><th>Reasons</th>
</tr>
</thead>
<tbody>
{% for case in result.cases %}
<tr>
  <td><code>{{ case.case_id }}</code></td>
  <td><span class="state-{{ case.state.value }}">{{ case.state.value }}</span></td>
  <td class="meta">
    {% if case_configs and case.case_id in case_configs %}
    <strong>Source:</strong> {{ case_configs[case.case_id].source_text }}<br>
    <strong>Expected:</strong> {{ case_configs[case.case_id].expected_transcript }}
    {% endif %}
  </td>
  <td>{% if highlighted[case.case_id] %}{{ highlighted[case.case_id][0]|safe }}{% else %}{{ case.baseline_transcript or "—" }}{% endif %}</td>
  <td>{% if highlighted[case.case_id] %}{{ highlighted[case.case_id][1]|safe }}{% else %}{{ case.candidate_transcript or "—" }}{% endif %}</td>
  <td>
    {% if baseline_audio[case.case_id] %}
    <audio controls src="data:audio/mpeg;base64,{{ baseline_audio[case.case_id] }}"></audio>
    {% else %}—{% endif %}
  </td>
  <td>
    {% if candidate_audio[case.case_id] %}
    <audio controls src="data:audio/mpeg;base64,{{ candidate_audio[case.case_id] }}"></audio>
    {% else %}—{% endif %}
  </td>
  <td class="meta">
    duration: {{ case.baseline_duration_ms or "?" }}ms → {{ case.candidate_duration_ms or "?" }}ms<br>
    lead sil: {{ case.baseline_leading_silence_ms or "?" }}ms → {{ case.candidate_leading_silence_ms or "?" }}ms<br>
    trail sil: {{ case.baseline_trailing_silence_ms or "?" }}ms → {{ case.candidate_trailing_silence_ms or "?" }}ms<br>
    latency: {{ case.generation_latency_ms or "?" }}ms<br>
    <details><summary>hashes</summary>
    base: {{ case.baseline_hash or "?" }}<br>cand: {{ case.candidate_hash or "?" }}
    </details>
  </td>
  <td>
    {% if case.reasons %}
    <ul class="reasons">
      {% for r in case.reasons %}<li><strong>{{ r.check }}</strong>: {{ r.detail }}</li>{% endfor %}
    </ul>
    {% else %}—{% endif %}
  </td>
</tr>
{% endfor %}
</tbody>
</table>
<p class="meta" style="margin-top:2rem">
  <em>REVIEW_REQUIRED requests inspection; it does not assert a TTS defect.
  ElevenLabs STT errors can appear as transcript fidelity differences.
  Listen to both clips before assigning cause.</em>
</p>
</body>
</html>"""


def render_report(
    result: RunResult,
    baseline_audio: dict[str, bytes],
    candidate_audio: dict[str, bytes],
    case_configs: dict | None = None,
) -> str:
    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(_TEMPLATE)

    def _b64(d: dict[str, bytes], key: str) -> str:
        data = d.get(key, b"")
        return base64.b64encode(data).decode() if data else ""

    b64_baseline = {k: _b64(baseline_audio, k) for k in [c.case_id for c in result.cases]}
    b64_candidate = {k: _b64(candidate_audio, k) for k in [c.case_id for c in result.cases]}

    highlighted: dict[str, tuple[str, str]] = {}
    for c in result.cases:
        if c.baseline_transcript is not None and c.candidate_transcript is not None:
            highlighted[c.case_id] = transcript_diff_pair(
                c.baseline_transcript, c.candidate_transcript
            )

    return tmpl.render(
        result=result,
        baseline_audio=b64_baseline,
        candidate_audio=b64_candidate,
        case_configs=case_configs or {},
        highlighted=highlighted,
    )
