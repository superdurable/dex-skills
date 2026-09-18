#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import re
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "plugins" / "dex" / "skills" / "dex-developer" / "references"
SOURCE_BLOCK = re.compile(
    r"<!-- dex-source: (?P<path>[^\s]+) -->\s*\n"
    r"```(?P<language>[^\n]*)\n(?P<snippet>.*?)\n```",
    re.DOTALL,
)
LANGUAGE_FENCE = re.compile(
    r"^```[ \t]*(?:go|python|java|typescript|ts|rust)(?:[ \t]+[^\n]*)?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
PINNED_LINK = re.compile(
    r"https://github\.com/superdurable/dex/(?P<kind>blob|tree)/(?P<target>[^)\s#]+)"
)


def fail(message: str) -> None:
    raise SystemExit(message)


def normalized(text: str) -> str:
    return textwrap.dedent(text).strip("\n")


def snippet_is_contiguous(source: str, snippet: str) -> bool:
    wanted = normalized(snippet)
    count = len(snippet.splitlines())
    source_lines = source.splitlines()
    for start in range(0, len(source_lines) - count + 1):
        candidate = "\n".join(source_lines[start:start + count])
        if normalized(candidate) == wanted:
            return True
    return False


def source_is_allowed(path: str) -> bool:
    source = Path(path)
    if source.is_absolute() or ".." in source.parts:
        return False
    if path == "examples" or path.startswith("examples/"):
        return True
    if not source.parts or source.parts[0] not in {
        "sdk-go",
        "sdk-java",
        "sdk-python",
        "sdk-rust",
        "sdk-typescript",
    }:
        return False
    if source.name.lower().startswith("readme"):
        return True
    if "test" in source.parts or "tests" in source.parts:
        return True
    return "_test." in source.name or source.name.endswith("Test.java")


def check_file(markdown: Path, dex_root: Path, baseline: str) -> int:
    content = markdown.read_text()
    blocks = list(SOURCE_BLOCK.finditer(content))
    marked_fences = {match.start("language") - 3 for match in blocks}
    for fence in LANGUAGE_FENCE.finditer(content):
        if fence.start() not in marked_fences:
            fail(f"unmarked language code fence in {markdown.relative_to(ROOT)}")

    for match in blocks:
        source_path = match.group("path")
        if not source_is_allowed(source_path):
            fail(f"unsupported source location in {markdown.relative_to(ROOT)}: {source_path}")
        source = (dex_root / source_path).resolve()
        try:
            source.relative_to(dex_root)
        except ValueError:
            fail(f"Dex source escapes checkout in {markdown.relative_to(ROOT)}: {source_path}")
        if not source.is_file():
            fail(f"missing Dex source for {markdown.relative_to(ROOT)}: {source_path}")
        preceding = content[max(0, match.start() - 600):match.start()]
        expected = f"https://github.com/superdurable/dex/blob/{baseline}/{source_path}"
        if expected not in preceding:
            fail(f"missing pinned source link before marker in {markdown.relative_to(ROOT)}")
        if not snippet_is_contiguous(source.read_text(), match.group("snippet")):
            fail(
                f"snippet in {markdown.relative_to(ROOT)} is not contiguous in "
                f"{source_path}"
            )

    for link in PINNED_LINK.finditer(content):
        expected_prefix = (
            f"https://github.com/superdurable/dex/{link.group('kind')}/{baseline}/"
        )
        if not link.group(0).startswith(expected_prefix):
            fail(f"Dex source link is not pinned to DEX_BASELINE in {markdown.relative_to(ROOT)}")
        linked_path = link.group(0)[len(expected_prefix):]
        if not source_is_allowed(linked_path):
            fail(f"unsupported Dex source link in {markdown.relative_to(ROOT)}: {linked_path}")
        resolved_link = (dex_root / linked_path).resolve()
        try:
            resolved_link.relative_to(dex_root)
        except ValueError:
            fail(f"Dex source link escapes checkout in {markdown.relative_to(ROOT)}")
        if not resolved_link.exists():
            fail(f"Dex source link path does not exist in {markdown.relative_to(ROOT)}")
    return len(blocks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dex-root", required=True, type=Path)
    arguments = parser.parse_args()

    baseline = (ROOT / "DEX_BASELINE").read_text().strip()
    dex_root = arguments.dex_root.resolve()
    if not (dex_root / ".git").exists():
        fail(f"not a Dex checkout: {dex_root}")
    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=dex_root,
        check=True,
        capture_output=True,
        text=True,
    )
    baseline_result = subprocess.run(
        ["git", "rev-parse", f"{baseline}^{{commit}}"],
        cwd=dex_root,
        check=True,
        capture_output=True,
        text=True,
    )
    if head_result.stdout.strip() != baseline_result.stdout.strip():
        fail(f"Dex checkout must be at DEX_BASELINE {baseline}")

    total = 0
    for markdown in sorted(REFERENCES.rglob("*.md")):
        total += check_file(markdown, dex_root, baseline)
    if total == 0:
        fail("expected at least one source-marked API excerpt")
    print(f"validated {total} source-marked excerpts against Dex {baseline}")


if __name__ == "__main__":
    main()
