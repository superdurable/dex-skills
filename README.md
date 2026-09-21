# Dex Skills

Dex Skills is the official agent-skill monorepo for building with
[Superdurable Dex](https://docs.superdurable.io). One `superdurable-dex` plugin
ships two skills for Codex, Claude Code, and Cursor:

| Skill | Responsibility |
| --- | --- |
| `dex-sdk` | Implement, debug, test, and operate Dex applications in Python, Go, Java, TypeScript, or Rust. |
| `dex-app-builder` | Discover, prototype, implement, and locally verify an end-to-end Dex AI Platform product with a Go backend. |

`dex-app-builder` loads the sibling `dex-sdk` guidance when backend work begins
and follows only its Core and Go references. Install the complete plugin so both
skills are present.

## Install

### Codex

```bash
codex plugin marketplace add superdurable/dex-skills
codex plugin add superdurable-dex@superdurable
```

Start a new task after installation. Invoke `$dex-sdk` for SDK work or
`$dex-app-builder` for the product workflow.

### Claude Code

Run inside Claude Code:

```text
/plugin marketplace add superdurable/dex-skills
/plugin install superdurable-dex@superdurable
/reload-plugins
```

Invoke `/superdurable-dex:dex-sdk` or
`/superdurable-dex:dex-app-builder`.

### Cursor

Import `https://github.com/superdurable/dex-skills` from **Customize → From
GitHub Repository**, then install `superdurable-dex`. The two skills appear as
`/dex-sdk` and `/dex-app-builder`.

Agent Skills clients can install the same bundle directly:

```bash
npx skills add superdurable/dex-skills --all
```

### Migrating from the old plugin

The former plugin ID `dex` and invocation `$dex-developer` were replaced by
`superdurable-dex` and `$dex-sdk`. Remove or update the old marketplace install,
install `superdurable-dex@superdurable`, and start a new task so the new skill
names are discovered.

## Dex SDK

`dex-sdk` uses progressive disclosure. Shared semantics live under
`dex-sdk/references/core/`, and each supported language has a matching handbook.
The skill inspects the project's installed SDK and version-matched runnable
sources before choosing exact APIs.

Exact source excerpts are pinned to the Dex release in `DEX_BASELINE`. CI checks
that every marked snippet remains a contiguous excerpt of its declared source.
The project dependency and lockfile remain authoritative when versions differ.

## Dex App Builder

`dex-app-builder` starts with business discovery: process maintainers, managers,
terminal users, permissions, triggers, actions, waits, approvals, recovery, and
audit requirements. It then decides whether Dex Web v2 is sufficient or a
custom frontend needs a React mock and explicit approval.

Backend implementation is Go-only, starts from
`superdurable/dex-template-basic-process`, and must satisfy strict Dex Web v2 /
FDG 2.0 rendering. Connector integrations reuse
`superdurable/dex-connectors-library` when a compatible implementation exists.
The workflow finishes with local tests and a clean handoff ready for future Dex
AI Platform upload; it does not claim that upload is available today.

## Releases

The two skills and all client manifests share the version in `VERSION`. A merge
to `main` creates GitHub Release `v<version>` when that tag does not already
exist. See [CONTRIBUTING.md](CONTRIBUTING.md) for validation and release rules.

## License

[MIT](LICENSE)
