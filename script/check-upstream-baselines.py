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


def require_ancestor(checkout: Path, ancestor: str, descendant: str, label: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=checkout,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{label} {ancestor} is not an ancestor of {descendant}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dex-root", required=True, type=Path)
    parser.add_argument("--template-root", required=True, type=Path)
    arguments = parser.parse_args()

    sdk_baseline = (ROOT / "DEX_BASELINE").read_text().strip()
    server_baseline = (ROOT / "DEX_SERVER_BASELINE").read_text().strip()
    dex_baseline = (ROOT / "DEX_WEB_V2_BASELINE").read_text().strip()
    template_baseline = (ROOT / "TEMPLATE_BASELINE").read_text().strip()
    require_revision(arguments.dex_root, dex_baseline, "Dex")
    require_revision(arguments.template_root, template_baseline, "template")
    require_ancestor(arguments.dex_root, sdk_baseline, dex_baseline, "Dex SDK baseline")
    require_ancestor(arguments.dex_root, server_baseline, dex_baseline, "Dex Server baseline")

    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "v2_directives.go",
        "GetDexSummary",
        "GetDexDisplay",
        "dex:group",
        "RPCOptions.Action",
        "ActionRequiresPermission",
        '"ui-slot"',
    )
    require_text(
        arguments.dex_root / "cli" / "README.md",
        "--schema-version 2.0",
        "Go-only",
    )
    require_text(
        arguments.dex_root / "web" / "api" / "v2.go",
        "V2PermissionModeTrustedHeader",
        "V2WorkQueuePermissionsHeader",
        "Action permission denied",
    )
    require_text(
        arguments.dex_root / "sdk-go" / "README.md",
        "Once a permission has",
        "remains searchable after completion",
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "go_connector_factory.go",
        "parseConnectorFactoryStep",
        '"connectionName"',
        '"moduleVersion"',
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "dev" / "config.go",
        "connector-config-dir",
    )
    require_text(
        arguments.dex_root / "web" / "connector_connection_store.go",
        "connections.json",
        "os.Rename",
    )
    require_text(
        arguments.dex_root / "web" / "connector_oauth.go",
        "code_verifier",
        'credentials["access_token"]',
    )

    template_manifest = json.loads(
        (arguments.template_root / ".superverse" / "template.json").read_text()
    )
    if template_manifest.get("templateVersion") != "1.3.0":
        fail("template baseline must be version 1.3.0")
    if template_manifest.get("commands", {}).get("checkFdgV2") != "make check-fdg-v2":
        fail("template baseline must expose checkFdgV2")
    if template_manifest.get("commands", {}).get("mock") != "make mock":
        fail("template baseline must expose mock")
    if template_manifest.get("commands", {}).get("testMockE2E") != "make test-mock-e2e":
        fail("template baseline must expose testMockE2E")
    template_dex_baseline = (
        arguments.template_root / "DEX_WEB_V2_BASELINE"
    ).read_text().strip()
    if template_dex_baseline != dex_baseline:
        fail("template Dex Web baseline must match Dex App Builder")
    template_server_baseline = (
        arguments.template_root / "DEX_SERVER_BASELINE"
    ).read_text().strip()
    if template_server_baseline != server_baseline:
        fail("template Dex Server baseline must match Dex App Builder")
    require_text(
        arguments.template_root / "go.mod",
        "github.com/superdurable/dex/sdk-go v0.11.3",
    )
    require_text(
        arguments.template_root / "internal" / "process" / "flow.go",
        "GetDexSummary",
        "GetDexDisplay",
        "ActionRequiresPermission",
        "// dex:group",
    )
    if "// dex:action" in (
        arguments.template_root / "internal" / "process" / "flow.go"
    ).read_text():
        fail("template must use typed Action registration without dex:action")
    print("validated Dex Server, Web v2, SDK, and basic-process template baselines")


if __name__ == "__main__":
    main()
