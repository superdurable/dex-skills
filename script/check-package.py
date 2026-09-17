#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "dex"
LOGO = PLUGIN / "assets" / "logo.png"
SKILL = PLUGIN / "skills" / "dex-developer"
REFERENCES = SKILL / "references"
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
CORE_TOPICS = {
    "error-handling.md",
    "getting-started.md",
    "modeling.md",
    "primitives.md",
    "patterns.md",
    "testing.md",
    "troubleshooting.md",
    "operations.md",
    "versioning.md",
    "data-handling.md",
    "ai-agents.md",
}
LANGUAGES = ("python", "go", "java", "typescript", "rust")
LANGUAGE_TOPICS = {
    "primitives.md",
    "patterns.md",
    "testing.md",
    "error-handling.md",
    "data-handling.md",
    "observability.md",
    "versioning.md",
    "gotchas.md",
    "advanced-features.md",
}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
FENCED_BLOCK = re.compile(r"```.*?```", re.DOTALL)
SOURCE_MARKER = re.compile(r"<!-- dex-source: ([^\s]+) -->")
FLOATING_SOURCE_LINK = re.compile(
    r"https://github\.com/superdurable/dex/(?:blob|tree)/main/"
)


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


def local_link_target(markdown: Path, target: str) -> Path | None:
    if "://" in target or target.startswith(("#", "mailto:")):
        return None
    relative_target = target.split("#", 1)[0].strip("<>")
    if not relative_target:
        return None
    return (markdown.parent / relative_target).resolve()


def check_reference_layout(markdown_files: list[Path]) -> None:
    core_files = {path.name for path in (REFERENCES / "core").glob("*.md")}
    if core_files != CORE_TOPICS:
        fail(f"core references must be exactly: {', '.join(sorted(CORE_TOPICS))}")

    for language in LANGUAGES:
        language_dir = REFERENCES / language
        expected = {*LANGUAGE_TOPICS, f"{language}.md"}
        actual = {path.name for path in language_dir.glob("*.md")}
        if actual != expected:
            fail(
                f"{language} references must be exactly: "
                f"{', '.join(sorted(expected))}"
            )

    unexpected_root_files = sorted(REFERENCES.glob("*.md"))
    if unexpected_root_files:
        rendered = ", ".join(path.name for path in unexpected_root_files)
        fail(f"references must be grouped under core or a language: {rendered}")

    expected_count = len(CORE_TOPICS) + len(LANGUAGES) * 10
    if len(markdown_files) != expected_count:
        fail(f"expected {expected_count} reference files, found {len(markdown_files)}")


def check_markdown_links(markdown_files: list[Path], baseline: str) -> None:
    all_markdown = [SKILL / "SKILL.md", *markdown_files]
    graph: dict[Path, set[Path]] = {path.resolve(): set() for path in all_markdown}

    for markdown in all_markdown:
        content = markdown.read_text()
        if FLOATING_SOURCE_LINK.search(content):
            fail(f"floating Dex source link in {markdown.relative_to(ROOT)}")
        prose = FENCED_BLOCK.sub("", content)
        for target in MARKDOWN_LINK.findall(prose):
            resolved = local_link_target(markdown, target)
            if resolved is None:
                continue
            if not resolved.exists():
                fail(f"broken link in {markdown.relative_to(ROOT)}: {target}")
            if resolved.suffix == ".md" and resolved in graph:
                graph[markdown.resolve()].add(resolved)

        for source_path in SOURCE_MARKER.findall(content):
            expected_link = (
                "https://github.com/superdurable/dex/blob/"
                f"{baseline}/{source_path}"
            )
            marker_position = content.index(f"<!-- dex-source: {source_path} -->")
            preceding = content[max(0, marker_position - 600):marker_position]
            if expected_link not in preceding:
                fail(
                    f"source marker in {markdown.relative_to(ROOT)} needs visible "
                    f"pinned link: {source_path}"
                )

    reachable: set[Path] = set()
    pending = [SKILL / "SKILL.md"]
    while pending:
        current = pending.pop().resolve()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(graph[current] - reachable)

    unreachable = sorted(path for path in markdown_files if path.resolve() not in reachable)
    if unreachable:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in unreachable)
        fail(f"references not reachable from SKILL.md: {rendered}")


def check_skill(baseline: str) -> None:
    skill_files = sorted(ROOT.glob("**/SKILL.md"))
    if skill_files != [SKILL / "SKILL.md"]:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in skill_files)
        fail(f"expected one canonical SKILL.md, found: {rendered}")

    markdown_files = sorted(REFERENCES.rglob("*.md"))
    check_reference_layout(markdown_files)
    check_markdown_links(markdown_files, baseline)


def check_manifests(version: str) -> None:
    for path in MANIFESTS:
        manifest = load_json(path)
        if manifest.get("name") != "dex":
            fail(f"{path.relative_to(ROOT)} must name plugin dex")
        if manifest.get("version") != version:
            fail(f"{path.relative_to(ROOT)} version must be {version}")

    if not LOGO.is_file() or not LOGO.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        fail("plugins/dex/assets/logo.png must be a PNG file")

    for path in (PLUGIN / "plugin.json", PLUGIN / ".codex-plugin" / "plugin.json"):
        interface = load_json(path).get("interface")
        if not isinstance(interface, dict):
            fail(f"{path.relative_to(ROOT)} must define interface metadata")
        for field in ("composerIcon", "logo"):
            if interface.get(field) != "./assets/logo.png":
                fail(f"{path.relative_to(ROOT)} {field} must use ./assets/logo.png")

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

    cursor_marketplace = load_json(ROOT / ".cursor-plugin" / "marketplace.json")
    cursor_plugin = cursor_marketplace["plugins"][0]
    if cursor_plugin.get("logo") != "plugins/dex/assets/logo.png":
        fail("Cursor marketplace must use plugins/dex/assets/logo.png")


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
    required = {"CHANGELOG.md", "VERSION"}
    missing = required - changed
    if missing:
        fail(f"skill changes must update: {', '.join(sorted(missing))}")
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
    baseline = (ROOT / "DEX_BASELINE").read_text().strip()
    if COMMIT_SHA.fullmatch(baseline) is None:
        fail("DEX_BASELINE must contain one lowercase 40-character commit SHA")
    check_skill(baseline)
    check_manifests(current_version)
    if arguments.base_ref:
        check_release_change(arguments.base_ref, current_version)
    print(f"validated dex plugin {current_version} at Dex baseline {baseline}")


if __name__ == "__main__":
    main()
