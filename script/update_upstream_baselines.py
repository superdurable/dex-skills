#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Update published upstream baselines and synchronized plugin versions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path


STABLE_VERSION = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CONNECTOR_TAG = re.compile(
    r"^(?:sdkgo|connectors/[a-z0-9][a-z0-9_/-]*)/v"
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)
PLUGIN_MANIFESTS = (
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
)
MARKETPLACE_MANIFESTS = (
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/marketplace.json",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_version(value: str, label: str) -> tuple[str, tuple[int, int, int]]:
    match = STABLE_VERSION.fullmatch(value.strip())
    if match is None:
        fail(f"{label} must be a stable semantic version, got: {value}")
    parts = tuple(int(part) for part in match.groups())
    return f"v{parts[0]}.{parts[1]}.{parts[2]}", parts


def component_tag(
    value: str, prefix: str, label: str
) -> tuple[str, str, tuple[int, int, int]]:
    if not value.startswith(prefix):
        fail(f"{label} must start with {prefix}, got: {value}")
    version, parts = canonical_version(value.removeprefix(prefix), label)
    return f"{prefix}{version}", version, parts


def replace_required(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    if old not in content:
        fail(f"{path} is missing expected value: {old}")
    path.write_text(content.replace(old, new))


def replace_repository_links(directory: Path, repository: str, old: str, new: str) -> None:
    prefixes = ("blob", "tree")
    replaced = 0
    for path in sorted(directory.rglob("*.md")):
        content = path.read_text()
        updated = content
        for kind in prefixes:
            updated = updated.replace(
                f"https://github.com/{repository}/{kind}/{old}/",
                f"https://github.com/{repository}/{kind}/{new}/",
            )
        if updated != content:
            path.write_text(updated)
            replaced += 1
    if replaced == 0:
        fail(f"no {repository} links referenced baseline {old}")


def update_json_version(path: Path, old: str, new: str, marketplace: bool) -> None:
    manifest = json.loads(path.read_text())
    if marketplace:
        plugins = manifest.get("plugins")
        if not isinstance(plugins, list) or len(plugins) != 1:
            fail(f"{path} must contain exactly one plugin")
        target = plugins[0]
    else:
        target = manifest
    if target.get("version") != old:
        fail(f"{path} version does not match VERSION {old}")
    target["version"] = new
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def bump_plugin_version(root: Path, release_date: str, bullets: list[str]) -> tuple[str, str]:
    current, current_parts = canonical_version(
        (root / "VERSION").read_text().strip(), "plugin version"
    )
    current_plain = current.removeprefix("v")
    next_plain = f"{current_parts[0]}.{current_parts[1]}.{current_parts[2] + 1}"
    (root / "VERSION").write_text(next_plain + "\n")
    for relative in PLUGIN_MANIFESTS:
        update_json_version(root / relative, current_plain, next_plain, False)
    for relative in MARKETPLACE_MANIFESTS:
        update_json_version(root / relative, current_plain, next_plain, True)

    changelog = root / "CHANGELOG.md"
    marker = "All notable changes to Dex Skills are documented here.\n\n"
    entry = (
        f"## {next_plain} - {release_date}\n\n"
        + "".join(f"- {bullet}\n" for bullet in bullets)
        + f"- Synchronize the Codex, Claude Code, and Cursor plugin manifests at version {next_plain}.\n\n"
    )
    replace_required(changelog, marker, marker + entry)
    return current_plain, next_plain


def require_not_older(
    latest: tuple[int, int, int], current: tuple[int, int, int], label: str
) -> None:
    if latest < current:
        fail(f"resolved {label} is older than the current baseline")


def update(
    root: Path,
    dex_tag: str,
    server_tag: str,
    cli_tag: str,
    template_tag: str,
    template_contract_version: str,
    template_sdk_version: str,
    connector_tag: str,
    release_date: str,
) -> dict[str, str]:
    latest_dex, latest_dex_version, latest_dex_parts = component_tag(
        dex_tag, "sdk-go/", "Dex SDK tag"
    )
    latest_server, latest_server_version, latest_server_parts = component_tag(
        server_tag, "server/", "Dex Server tag"
    )
    latest_cli, latest_cli_version, latest_cli_parts = component_tag(
        cli_tag, "cli-", "Dex CLI tag"
    )
    latest_template, latest_template_parts = canonical_version(
        template_tag, "basic-process template tag"
    )
    latest_template_contract, _ = canonical_version(
        template_contract_version, "basic-process template contract version"
    )
    latest_template_sdk, _ = canonical_version(
        template_sdk_version, "basic-process Dex Go SDK version"
    )
    if CONNECTOR_TAG.fullmatch(connector_tag) is None:
        fail(f"Connector Library tag is not a stable component release: {connector_tag}")

    current_dex, current_dex_version, current_dex_parts = component_tag(
        (root / "DEX_BASELINE").read_text().strip(),
        "sdk-go/",
        "current Dex SDK tag",
    )
    current_server, current_server_version, current_server_parts = component_tag(
        (root / "DEX_SERVER_BASELINE").read_text().strip(),
        "server/",
        "current Dex Server tag",
    )
    current_cli, current_cli_version, current_cli_parts = component_tag(
        (root / "DEX_CLI_BASELINE").read_text().strip(),
        "cli-",
        "current Dex CLI tag",
    )
    current_template, current_template_parts = canonical_version(
        (root / "TEMPLATE_BASELINE").read_text().strip(),
        "current basic-process template tag",
    )
    current_connector = (root / "CONNECTOR_LIBRARY_BASELINE").read_text().strip()
    if CONNECTOR_TAG.fullmatch(current_connector) is None:
        fail("current Connector Library baseline is not a stable component tag")

    require_not_older(latest_dex_parts, current_dex_parts, "Dex SDK tag")
    require_not_older(latest_server_parts, current_server_parts, "Dex Server tag")
    require_not_older(latest_cli_parts, current_cli_parts, "Dex CLI tag")
    require_not_older(latest_template_parts, current_template_parts, "template tag")

    dex_changed = latest_dex_parts > current_dex_parts
    server_changed = latest_server_parts > current_server_parts
    cli_changed = latest_cli_parts > current_cli_parts
    template_changed = latest_template_parts > current_template_parts
    connector_changed = connector_tag != current_connector
    bullets: list[str] = []

    if dex_changed:
        (root / "DEX_BASELINE").write_text(latest_dex + "\n")
        replace_repository_links(
            root / "dex-sdk", "superdurable/dex", current_dex, latest_dex
        )
        bullets.append(
            f"Upgrade the Dex SDK source baseline from `{current_dex}` to `{latest_dex}`."
        )
    if server_changed:
        (root / "DEX_SERVER_BASELINE").write_text(latest_server + "\n")
        replace_required(
            root / "README.md",
            f"Dex Server `{current_server_version}`",
            f"Dex Server `{latest_server_version}`",
        )
        bullets.append(
            f"Upgrade the Dex Server baseline from `{current_server}` to `{latest_server}`."
        )
    if cli_changed:
        (root / "DEX_CLI_BASELINE").write_text(latest_cli + "\n")
        replace_required(
            root / "README.md",
            f"Dex CLI `{current_cli_version}`",
            f"Dex CLI `{latest_cli_version}`",
        )
        bullets.append(
            f"Upgrade the Dex CLI baseline from `{current_cli}` to `{latest_cli}`."
        )
    if template_changed:
        (root / "TEMPLATE_BASELINE").write_text(latest_template + "\n")
        replace_required(
            root / "README.md",
            f"basic-process release `{current_template}`",
            f"basic-process release `{latest_template}`",
        )
        checker = root / "script" / "check-upstream-baselines.py"
        checker_content = checker.read_text()
        contract_match = re.search(
            r'template_manifest\.get\("templateVersion"\) != "(?P<value>\d+\.\d+\.\d+)"',
            checker_content,
        )
        sdk_match = re.search(
            r'github\.com/superdurable/dex/sdk-go v(?P<value>\d+\.\d+\.\d+)',
            checker_content,
        )
        if contract_match is None or sdk_match is None:
            fail("template contract assertions are missing from check-upstream-baselines.py")
        old_contract = contract_match.group("value")
        old_sdk = sdk_match.group("value")
        updated = checker_content.replace(
            f'templateVersion") != "{old_contract}"',
            f'templateVersion") != "{latest_template_contract.removeprefix("v")}"',
        ).replace(
            f"template baseline must be version {old_contract}",
            f"template baseline must be version {latest_template_contract.removeprefix('v')}",
        ).replace(
            f"github.com/superdurable/dex/sdk-go v{old_sdk}",
            f"github.com/superdurable/dex/sdk-go {latest_template_sdk}",
        )
        checker.write_text(updated)
        bullets.append(
            f"Upgrade the basic-process template baseline from `{current_template}` to `{latest_template}`."
        )
    if connector_changed:
        (root / "CONNECTOR_LIBRARY_BASELINE").write_text(connector_tag + "\n")
        replace_repository_links(
            root / "dex-connector-contributor",
            "superdurable/dex-connectors-library",
            current_connector,
            connector_tag,
        )
        bullets.append(
            f"Advance the Connector Library source snapshot from `{current_connector}` to `{connector_tag}`."
        )

    changed = any(
        (dex_changed, server_changed, cli_changed, template_changed, connector_changed)
    )
    current_plugin = (root / "VERSION").read_text().strip()
    next_plugin = current_plugin
    if changed:
        current_plugin, next_plugin = bump_plugin_version(root, release_date, bullets)

    return {
        "changed": str(changed).lower(),
        "dex_previous": current_dex,
        "dex_latest": latest_dex,
        "server_previous": current_server,
        "server_latest": latest_server,
        "cli_previous": current_cli,
        "cli_latest": latest_cli,
        "template_previous": current_template,
        "template_latest": latest_template,
        "connector_previous": current_connector,
        "connector_latest": connector_tag,
        "plugin_previous": current_plugin,
        "plugin_latest": next_plugin,
    }


def write_outputs(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    print(json.dumps(values, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dex-tag", required=True)
    parser.add_argument("--server-tag", required=True)
    parser.add_argument("--cli-tag", required=True)
    parser.add_argument("--template-tag", required=True)
    parser.add_argument("--template-contract-version", required=True)
    parser.add_argument("--template-sdk-version", required=True)
    parser.add_argument("--connector-tag", required=True)
    parser.add_argument("--release-date", default=dt.date.today().isoformat())
    arguments = parser.parse_args()
    values = update(
        Path(__file__).resolve().parents[1],
        arguments.dex_tag,
        arguments.server_tag,
        arguments.cli_tag,
        arguments.template_tag,
        arguments.template_contract_version,
        arguments.template_sdk_version,
        arguments.connector_tag,
        arguments.release_date,
    )
    write_outputs(values)


if __name__ == "__main__":
    main()
