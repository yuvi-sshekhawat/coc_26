from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BenchmarkRecord:
    instance: str
    status: str
    runtime_seconds: float
    minimum_service_ratio: float | None = None
    balance: float | None = None
    total_distance: int | None = None
    total_allocated: int | None = None
    validation_valid: bool | None = None
    error: str | None = None


def run_one(
    project_root: Path,
    instance_path: Path,
    module: str,
) -> BenchmarkRecord:
    started = time.perf_counter()

    try:
        proc = subprocess.run(
            [sys.executable, "-m", module, str(instance_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        elapsed = time.perf_counter() - started

        if proc.returncode != 0:
            return BenchmarkRecord(
                instance=instance_path.stem,
                status="FAILED",
                runtime_seconds=elapsed,
                error=proc.stderr[-4000:] or proc.stdout[-4000:],
            )

        # Stage modules print human-readable output. Parsing is intentionally
        # deferred to the final pipeline; this runner also records raw output.
        return BenchmarkRecord(
            instance=instance_path.stem,
            status="COMPLETED",
            runtime_seconds=elapsed,
        )

    except Exception as exc:
        return BenchmarkRecord(
            instance=instance_path.stem,
            status="FAILED",
            runtime_seconds=time.perf_counter() - started,
            error=str(exc),
        )


def write_manifest(path: Path, records: Iterable[BenchmarkRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(r) for r in records], indent=2),
        encoding="utf-8",
    )
