from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)

    (OUT / "code").mkdir(parents=True)
    (OUT / "results").mkdir(parents=True)
    (OUT / "documentation").mkdir(parents=True)

    keep_code = [
        "src",
        "scripts",
        "backend",
        "frontend",
        "data",
        "tests",
        "requirements.txt",
        "pyproject.toml",
        "README.md",
        "FINAL_REPORT.md",
    ]

    for rel in keep_code:
        src = ROOT / rel
        if not src.exists():
            continue
        dst = OUT / "code" / rel
        if src.is_dir():
            # Skip node_modules and cache directories
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("node_modules", ".pytest_cache", "__pycache__", "dist"),
            )
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    results = ROOT / "results"
    if results.exists():
        shutil.copytree(results, OUT / "results", dirs_exist_ok=True)

    docs = [
        ROOT / "FINAL_REPORT.md",
        ROOT / "README.md",
        ROOT / "README_FINAL.md",
        ROOT / "docs" / "FINAL_RUNBOOK.md",
    ]
    for doc in docs:
        if doc.exists():
            shutil.copy2(doc, OUT / "documentation" / doc.name)

    manifest = {
        "project": "AI-05 Fair Essential-Goods Allocation and Routing",
        "contains": [
            "full source code (src/ai05, backend, frontend)",
            "official CVRPLIB instance data (data/)",
            "authoritative validation layer (src/ai05/validation.py)",
            "benchmark runner & results for A-n32-k5, A-n33-k5, B-n31-k5 (results/)",
            "route outputs (routes.json, routes.txt)",
            "per-region service metrics and balance",
            "visualizations (routes.png, regional_service.png, allocation.png)",
            "FastAPI backend & Neo-brutalist React dashboard",
            "comprehensive test suite (tests/)",
            "FINAL_REPORT.md",
        ],
    }
    (OUT / "submission_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    # Also build a zip archive for convenience
    zip_path = ROOT / "submission_bundle"
    shutil.make_archive(str(zip_path), "zip", str(OUT))
    print(f"Submission bundle created at: {OUT}")
    print(f"Zip archive created at: {zip_path}.zip")


if __name__ == "__main__":
    main()
