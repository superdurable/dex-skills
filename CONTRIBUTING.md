# Contributing

This repository publishes one plugin with two root-level skills:

- `dex-sdk` owns public Dex SDK implementation guidance and its Core and
  language references.
- `dex-app-builder` owns the business-first product workflow and platform-only
  constraints. It links to `dex-sdk` instead of copying SDK references.

Keep every reference reachable from its skill entrypoint. Do not add a
`plugins/` wrapper, a backend companion skill, or duplicated Core/Go handbooks.

## Pin source authority

`DEX_BASELINE` pins exact SDK excerpts. Language code fences must be contiguous
excerpts from runnable examples, SDK tests, or SDK READMEs at that release, with
the existing visible source link and `dex-source` marker.

`DEX_SERVER_BASELINE` pins the released Server required by App Builder.
`DEX_CLI_BASELINE` pins the released local tooling and embedded Web v2/FDG 2.0
implementation. The Server release embeds the same Dex Web source for hosted
environments.
`TEMPLATE_BASELINE` pins the published release of the only supported
application template. Refresh any baseline deliberately and review all affected
guidance.

## Validate a change

Run from the repository root:

```bash
python3 script/check-package.py
python3 script/check-reference-sources.py --dex-root /path/to/dex-sdk-baseline
python3 script/check-upstream-baselines.py \
  --dex-root /path/to/dex-cli-baseline \
  --template-root /path/to/dex-template-basic-process
python3 /path/to/skill-creator/scripts/quick_validate.py dex-sdk
python3 /path/to/skill-creator/scripts/quick_validate.py dex-app-builder
```

Also validate the Codex, Claude Code, and Cursor manifests with their current
client tooling and smoke-test that one plugin install exposes exactly the two
expected skills. For `dex-app-builder`, confirm the backend stage resolves the
sibling `dex-sdk` Go handbook without copied references.

## Version and release

Every change under `dex-sdk/` or `dex-app-builder/` updates `VERSION` and
`CHANGELOG.md`. Keep every plugin and marketplace manifest on that exact
version where the format supports a version.

- Increment PATCH for corrections and clarifications.
- Increment MINOR for new product workflows, languages, patterns, or other
  backward-compatible capabilities.
- Increment MAJOR for incompatible plugin or skill identity changes.

After a pull request lands on `main`, the Release workflow validates the full
package and creates `v<version>` from the matching changelog section. If the tag
already exists, the workflow skips release creation.
