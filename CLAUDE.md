# Dex Skills Repository Instructions

This repository publishes one `superdurable-dex` plugin for Codex, Claude Code,
and Cursor. Its only public skills are `dex-sdk` and `dex-app-builder`, stored
directly at the repository root.

## Skill boundaries

- `dex-sdk` is the technical capability layer for implementing, debugging,
  testing, and operating applications through the public Dex SDK.
- `dex-app-builder` is the end-to-end product workflow for business discovery,
  an explicit no-custom-UI or custom-UI decision, Go backend implementation,
  local testing, and Dex AI Platform handoff.
- During backend implementation, `dex-app-builder` loads `dex-sdk` and follows
  only its Core and Go guidance. Do not duplicate those references.
- Platform constraints are stricter: Go only, strict FDG 2.0, provider effects
  only in `Execute`, and no provider or Dex mutations in `WaitFor`.

## Packaging and release

Keep Codex, Claude Code, and Cursor manifests synchronized on plugin ID,
version, repository, skill paths, and display metadata. Do not reintroduce a
`plugins/` wrapper or a third backend skill.

Every skill change updates `VERSION` and `CHANGELOG.md`. Validate Dex SDK source
excerpts against `DEX_BASELINE`, and validate Server, CLI, and the basic-process
template against `DEX_SERVER_BASELINE`, `DEX_CLI_BASELINE`, and
`TEMPLATE_BASELINE`. Dex Web is embedded in the Server and CLI releases.
