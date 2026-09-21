#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SOURCE_PREFIX = "plugins/dex/skills/dex-developer/references"
PLATFORM_REFERENCES = Path(
    "plugins/dex-ai-platform/skills/dex-ai-platform-backend/references"
)
SYNC_MANIFEST = "DEX_DEVELOPER_SYNC.json"
PAIR = re.compile(
    r"(?m)^Dex-AI-Platform-PR:\s*"
    r"https://github\.com/superdurable/skill-dex-ai-platform/pull/(\d+)\s*$"
)


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


def git_bytes(root: Path, revision: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def paired_platform_pr(body: str) -> int:
    matches = PAIR.findall(body or "")
    if len(matches) != 1:
        fail("pull request body must contain exactly one Dex-AI-Platform-PR field")
    return int(matches[0])


def event(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid GitHub event: {error}")


def source_snapshot(root: Path, revision: str) -> tuple[dict, dict[str, bytes]]:
    commit = git(root, "rev-parse", f"{revision}^{{commit}}")
    tree = git(root, "rev-parse", f"{commit}:plugins/dex/skills/dex-developer")
    version = git_bytes(root, commit, "VERSION").decode().strip()
    baseline = git_bytes(root, commit, "DEX_BASELINE").decode().strip()
    files: dict[str, bytes] = {}
    for section in ("core", "go"):
        prefix = f"{SOURCE_PREFIX}/{section}"
        listing = git(root, "ls-tree", "-r", "--name-only", commit, "--", prefix)
        for name in listing.splitlines():
            if name.endswith(".md"):
                relative = str(Path(name).relative_to(SOURCE_PREFIX))
                files[relative] = git_bytes(root, commit, name)
    metadata = {
        "sourceCommit": commit,
        "skillTree": tree,
        "version": version,
        "dexBaseline": baseline,
    }
    return metadata, files


def verify(
    source: Path,
    platform: Path,
    revision: str,
    source_pr: int | None,
    require_exact_commit: bool,
) -> None:
    source = source.resolve()
    platform = platform.resolve()
    manifest = json.loads((platform / SYNC_MANIFEST).read_text())
    metadata, files = source_snapshot(source, revision)

    for key in ("skillTree", "version", "dexBaseline"):
        if manifest.get(key) != metadata[key]:
            fail(f"platform {key} does not match Dex Developer")
    if require_exact_commit and manifest.get("sourceCommit") != metadata["sourceCommit"]:
        fail("platform sourceCommit does not match the pull request head")
    if source_pr is not None and manifest.get("sourcePr") != source_pr:
        fail("platform sourcePr does not match the Dex Developer pull request")

    hashes = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in sorted(files.items())
    }
    if manifest.get("files") != hashes:
        fail("platform vendored file manifest does not match Dex Developer")

    destination = platform / PLATFORM_REFERENCES
    actual = {
        str(path.relative_to(destination))
        for section in ("core", "go")
        for path in (destination / section).glob("*.md")
    }
    if actual != set(files):
        fail("platform vendored file set does not match Dex Developer")
    for name, content in files.items():
        if (destination / name).read_bytes() != content:
            fail(f"platform vendored reference differs: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--platform-root", type=Path)
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--source-pr", type=int)
    parser.add_argument("--github-event", type=Path)
    parser.add_argument("--print-platform-pr", action="store_true")
    parser.add_argument("--main", action="store_true")
    arguments = parser.parse_args()

    event_data = event(arguments.github_event) if arguments.github_event else {}
    pull_request = event_data.get("pull_request") or {}
    body = pull_request.get("body") or ""
    linked_pr = paired_platform_pr(body) if body else None

    if arguments.print_platform_pr:
        if linked_pr is None:
            fail("GitHub event does not contain a pull request body")
        print(linked_pr)
        return

    if arguments.source is None or arguments.platform_root is None:
        fail("--source and --platform-root are required for validation")

    source_pr = arguments.source_pr
    if source_pr is None and pull_request:
        source_pr = int(pull_request["number"])
    if pull_request and linked_pr is None:
        fail("missing paired Dex AI Platform pull request")

    verify(
        arguments.source,
        arguments.platform_root,
        arguments.source_commit,
        source_pr,
        require_exact_commit=not arguments.main,
    )
    print("validated Dex AI Platform bundled backend synchronization")


if __name__ == "__main__":
    main()
