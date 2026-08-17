# TTS Snapshot CI Progress

**Current phase:** CLI implementation verified; GitHub Action and demo documentation pending
**Last updated:** 2026-08-17

## Last Verified Working

2026-08-17: `pytest -q` passed (56 tests). A live ElevenLabs baseline and candidate comparison using the Free-tier George voice (`JBFqnCBsd6RMkjVDRZzb`) produced `PASS`; the report was rendered at `runs/20260817T175540Z-d60fce/report.html` with baseline and candidate audio artifacts.

## Built And Verified

- [x] Product direction selected: rendered-speech snapshot review CI.
- [x] CLI-first sequence approved; GitHub Action work is blocked until the CLI completion gate passes.
- [x] Three-state result model approved: `PASS`, `REVIEW_REQUIRED`, and `ERROR`.
- [x] Four-check contract approved: transcript fidelity, required phrases, duration drift, and leading/trailing silence drift.
- [x] Git-tracked baseline ownership and explicit named approval lifecycle approved.
- [x] Product, architecture, and snapshot contract documented.
- [x] Python CLI implemented: `snapshot record`, `snapshot check`, and `snapshot approve`.
- [x] Unit and regression suite passed: 56 tests.
- [x] Live ElevenLabs baseline recording and `PASS` comparison verified with rendered HTML report.
- [x] Windows audio measurement verified with FFmpeg/FFprobe installed and audio measured in memory.

Verification note: these items reflect design decisions approved in the project session on 2026-08-17. They do not claim implementation verification.

## In Progress

- [ ] Verify live `REVIEW_REQUIRED`, controlled `ERROR`, and approval-audit scenarios.
- [ ] Add README installation, configuration, and demo instructions.
- [ ] Add the GitHub Action wrapper after the complete CLI gate passes.

## Next Up

- [ ] Expand the live suite from one case to 5-10 short representative clips.
- [ ] Calibrate initial thresholds against the expanded live suite.
- [ ] Complete the remaining CLI completion-gate scenarios.

## Open Decisions

- Set initial transcript, duration, and silence thresholds using the first 5-10 real clips.
- Decide whether the demo should rely on the Free-tier George voice or document a user-selected account voice.

## Known Issues And Risks

- ElevenLabs STT can create false transcript-fidelity review items.
- Generated audio may vary byte-for-byte across identical requests.
- API latency varies with network and provider load and cannot be a reliable build gate.
- Git-tracked audio can grow the repository if the suite expands beyond the intended MVP size.
- The existing `VoiceRouter_Project_Spec.md` describes a superseded CRM concept and is not the active scope.

## Scope Guard

Do not create GitHub Action YAML until a real CLI run satisfies every completion-gate item in `PROJECT.md`. Move requests outside `PROJECT.md` to future work unless the project scope is explicitly revised.
