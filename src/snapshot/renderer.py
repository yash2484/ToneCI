# src/snapshot/renderer.py
from __future__ import annotations
import base64
from jinja2 import Environment, BaseLoader
from snapshot.models import RunResult

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
  <td>{{ case.baseline_transcript or "—" }}</td>
  <td>{{ case.candidate_transcript or "—" }}</td>
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

    return tmpl.render(
        result=result,
        baseline_audio=b64_baseline,
        candidate_audio=b64_candidate,
        case_configs=case_configs or {},
    )
