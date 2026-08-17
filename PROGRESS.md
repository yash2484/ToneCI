# TTS Snapshot CI Progress

**Current phase:** Design approved; implementation planning not started  
**Last updated:** 2026-08-17

## Last Verified Working

No application code exists yet. No tests, builds, API calls, or end-to-end checks have run.

## Built And Verified

- [x] Product direction selected: rendered-speech snapshot review CI.
- [x] CLI-first sequence approved; GitHub Action work is blocked until the CLI completion gate passes.
- [x] Three-state result model approved: `PASS`, `REVIEW_REQUIRED`, and `ERROR`.
- [x] Four-check contract approved: transcript fidelity, required phrases, duration drift, and leading/trailing silence drift.
- [x] Git-tracked baseline ownership and explicit named approval lifecycle approved.
- [x] Product, architecture, and snapshot contract documented.

Verification note: these items reflect design decisions approved in the project session on 2026-08-17. They do not claim implementation verification.

## In Progress

- [ ] User review of the written project and design documents.

## Next Up

- [ ] Create a detailed implementation plan after written-design approval.
- [ ] Define package metadata and dependencies in `pyproject.toml`.
- [ ] Implement typed case configuration and result models.
- [ ] Develop pure comparison logic with tests.
- [ ] Complete and verify the CLI before creating GitHub Action YAML.

## Open Decisions

- Choose the local audio-analysis library during implementation planning.
- Choose whether reports embed short audio clips or copy portable relative assets after a browser probe.
- Set initial transcript, duration, and silence thresholds using the first 5-10 real clips.
- Choose the exact package and command name if `snapshot` conflicts with an installed executable.

## Known Issues And Risks

- ElevenLabs STT can create false transcript-fidelity review items.
- Generated audio may vary byte-for-byte across identical requests.
- API latency varies with network and provider load and cannot be a reliable build gate.
- Git-tracked audio can grow the repository if the suite expands beyond the intended MVP size.
- The existing `VoiceRouter_Project_Spec.md` describes a superseded CRM concept and is not the active scope.

## Scope Guard

Do not create GitHub Action YAML until a real CLI run satisfies every completion-gate item in `PROJECT.md`. Move requests outside `PROJECT.md` to future work unless the project scope is explicitly revised.
