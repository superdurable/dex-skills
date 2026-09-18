# Contributing

The canonical skill is `plugins/dex/skills/dex-developer/SKILL.md`. Shared
semantics belong in `references/core/`. Language-native APIs belong in the
matching Python, Go, Java, TypeScript, or Rust directory. Keep all references
reachable from the skill entrypoint through progressive-disclosure links.

Each language directory has the same ten topics: its language entry,
primitives, patterns, testing, error handling, data handling, observability,
versioning, gotchas, and advanced features. When public behavior changes,
review all five handbooks and update every affected language in the same pull
request. Do not fill a parity gap with an invented API; identify the missing
runnable implementation instead.

## Pin API sources

`DEX_BASELINE` contains the immutable Dex release tag used for exact API excerpts.
Language code fences must be copied as contiguous excerpts from runnable
examples, SDK tests, or SDK READMEs at that tag. Put a visible pinned link
and machine-readable marker immediately before each excerpt:

```text
[Runnable source](https://github.com/superdurable/dex/blob/<DEX_BASELINE>/examples/...)
<!-- dex-source: examples/... -->
```

Refresh the baseline deliberately: fetch Dex, review changes since the previous
tag, update every affected excerpt and link, then run source-fidelity validation
against a checkout at the new tag. Never use a floating `main` link for an
exact API source.

## Validate a change

Run the repository checks from the root:

```bash
python3 script/check-package.py
python3 script/check-reference-sources.py --dex-root /path/to/dex
python3 /path/to/skill-creator/scripts/quick_validate.py \
  plugins/dex/skills/dex-developer
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/dex
claude plugin validate .
```

The last three commands require the corresponding agent tooling. CI runs the
package checks and checks out `DEX_BASELINE` to verify paths and excerpts.

Before a MINOR release, run five isolated behavior evaluations. Give each agent
only a realistic language-specific request, the packaged skill, and read-only
Dex source. Check routing, version verification, real APIs, Flow modeling,
failure recovery, and executable testing. Fix guidance and rerun failed
scenarios before release.

## Version a change

Every change under `plugins/dex/skills/dex-developer/` must update `VERSION` and
`CHANGELOG.md` in the same pull request. Keep all plugin manifests on the exact
version in `VERSION`.

- Increment PATCH for corrections and clarifications.
- Increment MINOR for new languages, patterns, or capabilities.
- Increment MAJOR for incompatible identity, invocation, or behavior changes.

Do not put a version on marketplace entries. The plugin manifests are the only
package version source.

## Release

For a MINOR release, validate the package and pinned source, smoke-test Codex,
Claude Code, Cursor, and `npx skills add`, and complete the five language
evaluations. The pull request remains a draft until CI and those checks pass.

Before creating any release, run all validation commands, install each package
locally, and test the skill in a new agent task or reloaded session. Tag the
validated commit as `v<version>` only after the pull request is merged and the
manifests, changelog, and documentation agree.
