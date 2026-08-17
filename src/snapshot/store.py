# src/snapshot/store.py
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from snapshot.models import BaselineManifest, RunResult


class ArtifactStore:
    def __init__(self, snapshots_dir: Path, runs_dir: Path) -> None:
        self._snap = snapshots_dir
        self._runs = runs_dir

    def _case_dir(self, case_id: str) -> Path:
        return self._snap / case_id

    def _run_dir(self, run_id: str) -> Path:
        return self._runs / run_id

    def baseline_exists(self, case_id: str) -> bool:
        return (self._case_dir(case_id) / "baseline.mp3").exists()

    def read_baseline_audio(self, case_id: str) -> bytes:
        return (self._case_dir(case_id) / "baseline.mp3").read_bytes()

    def read_baseline_manifest(self, case_id: str) -> BaselineManifest:
        raw = (self._case_dir(case_id) / "manifest.json").read_text(encoding="utf-8")
        return BaselineManifest.model_validate_json(raw)

    def write_baseline(self, case_id: str, audio: bytes, manifest: BaselineManifest) -> None:
        dest = self._case_dir(case_id) / "baseline.mp3"
        if dest.exists():
            raise FileExistsError(
                f"Baseline already exists for {case_id!r}. Use check -> approve to replace it."
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        (self._case_dir(case_id) / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )

    def new_run_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{secrets.token_hex(3)}"

    def write_candidate(self, run_id: str, case_id: str, audio: bytes) -> Path:
        dest = self._run_dir(run_id) / "candidates" / f"{case_id}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        return dest

    def read_candidate(self, run_id: str, case_id: str) -> bytes:
        return (self._run_dir(run_id) / "candidates" / f"{case_id}.mp3").read_bytes()

    def write_run_results(self, run_id: str, result: RunResult) -> None:
        dest = self._run_dir(run_id) / "results.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def read_run_results(self, run_id: str) -> RunResult:
        raw = (self._run_dir(run_id) / "results.json").read_text(encoding="utf-8")
        return RunResult.model_validate_json(raw)

    def write_report(self, run_id: str, html: str) -> Path:
        dest = self._run_dir(run_id) / "report.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        return dest

    def promote_candidate_to_baseline(
        self, run_id: str, case_id: str, new_manifest: BaselineManifest
    ) -> None:
        audio = self.read_candidate(run_id, case_id)
        dest_audio = self._case_dir(case_id) / "baseline.mp3"
        dest_audio.parent.mkdir(parents=True, exist_ok=True)
        dest_audio.write_bytes(audio)
        (self._case_dir(case_id) / "manifest.json").write_text(
            new_manifest.model_dump_json(indent=2), encoding="utf-8"
        )
