#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "dex"
SKILL = PLUGIN / "skills" / "dex-developer"
MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / ".claude-plugin" / "plugin.json",
)
MARKETPLACES = (
    ROOT / ".agents" / "plugins" / "marketplace.json",
    ROOT / ".claude-plugin" / "marketplace.json",
    ROOT / ".cursor-plugin" / "marketplace.json",
)
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {error}")


def version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(version)
    if match is None:
        fail(f"VERSION must be stable SemVer: {version}")
    return tuple(int(part) for part in match.groups())


def check_skill() -> None:
    skill_files = sorted(ROOT.glob("**/SKILL.md"))
    if skill_files != [SKILL / "SKILL.md"]:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in skill_files)
        fail(f"expected one canonical SKILL.md, found: {rendered}")

    markdown_files = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
    for markdown in markdown_files:
        text = markdown.read_text()
        for target in MARKDOWN_LINK.findall(text):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            relative_target = target.split("#", 1)[0]
            if relative_target and not (markdown.parent / relative_target).exists():
                fail(f"broken link in {markdown.relative_to(ROOT)}: {relative_target}")


def check_manifests(version: str) -> None:
    for path in MANIFESTS:
        manifest = load_json(path)
        if manifest.get("name") != "dex":
            fail(f"{path.relative_to(ROOT)} must name plugin dex")
        if manifest.get("version") != version:
            fail(f"{path.relative_to(ROOT)} version must be {version}")

    for path in MARKETPLACES:
        marketplace = load_json(path)
        if marketplace.get("name") != "superdurable":
            fail(f"{path.relative_to(ROOT)} must name marketplace superdurable")
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or len(plugins) != 1:
            fail(f"{path.relative_to(ROOT)} must contain one plugin")
        plugin = plugins[0]
        if plugin.get("name") != "dex" or "version" in plugin:
            fail(f"{path.relative_to(ROOT)} must expose unversioned plugin dex")
        source = plugin.get("source")
        source_path = source.get("path") if isinstance(source, dict) else source
        if source_path not in {"./plugins/dex", "plugins/dex"}:
            fail(f"{path.relative_to(ROOT)} must point to plugins/dex")


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def check_release_change(base_ref: str, current_version: str) -> None:
    changed = set(git_output("diff", "--name-only", f"{base_ref}...HEAD").splitlines())
    skill_prefix = "plugins/dex/skills/dex-developer/"
    if not any(path.startswith(skill_prefix) for path in changed):
        return
    if "CHANGELOG.md" not in changed or "VERSION" not in changed:
        fail("skill changes must update VERSION and CHANGELOG.md")
    try:
        base_version = git_output("show", f"{base_ref}:VERSION").strip()
    except subprocess.CalledProcessError:
        return
    if version_tuple(current_version) <= version_tuple(base_version):
        fail(f"VERSION must increase beyond {base_version}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    arguments = parser.parse_args()

    current_version = (ROOT / "VERSION").read_text().strip()
    version_tuple(current_version)
    check_skill()
    check_manifests(current_version)
    if arguments.base_ref:
        check_release_change(arguments.base_ref, current_version)
    print(f"validated dex plugin {current_version}")


if __name__ == "__main__":
    main()
