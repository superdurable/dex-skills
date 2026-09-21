#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(message)


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_revision(checkout: Path, expected: str, label: str) -> None:
    checkout = checkout.resolve()
    if not (checkout / ".git").exists():
        fail(f"{label} is not a Git checkout: {checkout}")
    actual = git(checkout, "rev-parse", "HEAD")
    resolved = git(checkout, "rev-parse", f"{expected}^{{commit}}")
    if actual != resolved:
        fail(f"{label} checkout {actual} does not match baseline {resolved}")


def require_text(path: Path, *needles: str) -> None:
    content = path.read_text()
    for needle in needles:
        if needle not in content:
            fail(f"{path} is missing required text: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dex-root", required=True, type=Path)
    parser.add_argument("--template-root", required=True, type=Path)
    arguments = parser.parse_args()

    dex_baseline = (ROOT / "DEX_WEB_V2_BASELINE").read_text().strip()
    template_baseline = (ROOT / "TEMPLATE_BASELINE").read_text().strip()
    require_revision(arguments.dex_root, dex_baseline, "Dex")
    require_revision(arguments.template_root, template_baseline, "template")

    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "v2_directives.go",
        "GetDexSummary",
        "GetDexDisplay",
        "dex:group",
        "dex:action",
    )
    require_text(
        arguments.dex_root / "cli" / "README.md",
        "--schema-version 2.0",
        "Go-only",
    )

    template_manifest = json.loads(
        (arguments.template_root / ".superverse" / "template.json").read_text()
    )
    if template_manifest.get("templateVersion") != "1.1.0":
        fail("template baseline must be version 1.1.0")
    if template_manifest.get("commands", {}).get("checkFdgV2") != "make check-fdg-v2":
        fail("template baseline must expose checkFdgV2")
    if (
        arguments.template_root / "DEX_WEB_V2_BASELINE"
    ).read_text().strip() != dex_baseline:
        fail("template and skill must pin the same Dex Web v2 baseline")
    require_text(
        arguments.template_root / "internal" / "process" / "flow.go",
        "GetDexSummary",
        "GetDexDisplay",
        "// dex:action",
        "// dex:group",
    )
    print("validated Dex Web v2 and basic-process template baselines")


if __name__ == "__main__":
    main()
