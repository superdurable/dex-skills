# RunID transparency guidance — source validation, 2026-09-30

## Scope

Source repository: `git@github.com:superdurable/dex-skills.git`, checked before
editing. Local source HEAD: `61857e181b1bcdc5a6a5ee3ba69b1013035991b9`.
This is a documentation/packaging change only. It does not modify the installed
plugin cache, any Dex/V2 runtime, SDK signatures, provider resources, dependency
pins or Flow schemas. No release or installation was performed. The coordinating owner stages only this
RunID guidance delta for a source checkpoint; unrelated in-progress edits remain
outside that commit.
The mixed worktree contained a separate uncommitted 0.25.12 change. The isolated
checkpoint advances committed metadata from 0.25.11 to 0.25.13 without staging
that unrelated work;
this is not a claim that 0.25.13 has been published or installed.

## Guidance changes

Ordinary business contracts use stable FlowID/business IDs, durable sequence/
revision state and operation IDs. RunID is absent from normal APIs, application
RPC payloads/DTOs, cursors, UI state and effect identities. Continue-As-New does
not restart the business, clear its history/approvals or rotate an effect key.
Diagnostics, engine history and authorized exact-execution recovery retain RunID.
Actual SDK return values and positional parameters remain truthful; no invented
signature, current-run helper or GetFlowSummary replacement poll is introduced.

The existing runnable language examples already address FlowID/registered Streams
and were preserved byte-for-byte. Surrounding guidance covers all five languages,
including TypeScript's real positional RPC run-selector overload. Agent progress
is reconciled with durable business message identity; token loss and provisional
text do not turn Streams into committed conversation history.

## Source evidence

Read immutable Dex commit `eccc88783e9254a6fe8c45ecdb66eb12e080afaa` from an
existing local official checkout using read-only `git show <commit>:<path>`.
`streamstore.WriteInput`, Redis instance keys and memory-store reads scope Streams
by FlowType, FlowID and StreamName. `resumeToken` contains Version, FlowID,
FlowType, StreamName and MessageID; encode/decode has no RunID. Read/list SDK and
server request paths have no run selector. The TypeScript RPC implementation
retains its optional positional run selector; ordinary callers omit it/use empty.
The Go typed InvokeRPC surface remains unchanged. Run-specific engine history and
internal metadata are not claimed to have been removed.

The verified source bytes were:

| Path at that commit | SHA256 |
| --- | --- |
| `server/service/common/streamstore/store.go` | `4572801a2b3a3110cf93f75aa4938528f878852388e052c369c1049d1cce9a57` |
| `server/service/common/streamstore/memory.go` | `3f3a414d5174398717af70c8d46f76c920acb2a11e1fb6444c03a4db8833146f` |
| `server/service/api/service.go` | `087dcc3ae72bd4a7e1cca4ad8b8e71cc13906c140a1a3aee83e959325fc12e4f` |
| `sdk-go/dex/client.go` | `c678f6cced9e6049021ee469d47d6bae2ed8446a119b3cba83a7af91b4ec6c90` |
| `sdk-typescript/src/client.ts` | `d2c2c9a3ea0afbabe7af2c23bca0af5e36222c1010b9424a8e69228375508b91` |

The broader skill baselines remain SDK `sdk-go/v0.13.1` (commit
`548208768eb77c80fed66710496f438302792b22`), Server `server/v0.13.2`, CLI
`cli-v0.13.8`, and template `v1.6.1`. The supplemental Stream evidence above does
not silently upgrade those pins.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 python3 script/check-package.py`: passed, all three
  root skills and synchronized plugin/marketplace version metadata.
- `PYTHONDONTWRITEBYTECODE=1 python3 script/check-reference-sources.py --dex-root
  /private/tmp/dex-attribute-sdk-baseline`: passed, all 98 marked excerpts against
  exact SDK baseline. No excerpt or API call signature changed.
- `PYTHONDONTWRITEBYTECODE=1 python3 script/check-upstream-baselines.py --dex-root
  /private/tmp/dex-baseline-cli-20260928-002 --template-root
  /private/tmp/template-baseline-20260928-002`: passed against existing exact
  Server/CLI/template checkouts, with no fetch or checkout mutation.
- Installed skill-creator `quick_validate.py dex-app-builder`: passed.
- The same generic validator for `dex-sdk` rejected its **pre-existing**
  `disable-model-invocation` frontmatter property. It accepts fewer keys than this
  repository's packaging rules; that explicit-only invocation setting was kept.
  The owning package validator accepts and checks it. No validator was weakened.
- Read-only review of RunID occurrences preserved diagnostic/error/history uses;
  the ordinary Agent snapshot recommendation and Rust response wording were
  corrected. No runtime, mock/unit or provider tests were run, and these static
  results are not application Continue-As-New acceptance evidence.

## Exact changed paths

- `.claude-plugin/marketplace.json`
- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- `.cursor-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`
- `CHANGELOG.md`
- `VERSION`
- `dex-app-builder/SKILL.md`
- `dex-sdk/SKILL.md`
- `dex-sdk/VERSION`
- `dex-sdk/references/core/ai-agents.md`
- `dex-sdk/references/core/operations.md`
- `dex-sdk/references/core/primitives.md`
- `dex-sdk/references/core/versioning.md`
- `dex-sdk/references/go/primitives.md`
- `dex-sdk/references/go/versioning.md`
- `dex-sdk/references/java/observability.md`
- `dex-sdk/references/java/primitives.md`
- `dex-sdk/references/java/versioning.md`
- `dex-sdk/references/python/primitives.md`
- `dex-sdk/references/python/versioning.md`
- `dex-sdk/references/rust/observability.md`
- `dex-sdk/references/rust/primitives.md`
- `dex-sdk/references/rust/versioning.md`
- `dex-sdk/references/typescript/advanced-features.md`
- `dex-sdk/references/typescript/primitives.md`
- `dex-sdk/references/typescript/versioning.md`
- `run-id-transparency-validation-2026-09-30.md` (this receipt)

Original licenses, skill routing and standalone-bundle link boundaries remain.
Git publication and any runtime dependency/installed-skill update are separate
owner actions. Full product CAN/reconnect/authorization behavior is not validated
by this source-only documentation checkpoint.

## Isolated checkpoint validation

The coordinator recreated HEAD in a private directory and applied only the owned
RunID guidance patch, adjusting its metadata context to the committed 0.25.11.
The 0.25.13 changelog contains only this change; the unrelated 0.25.12 entry and
connector-contributor/rules/workflow edits remain outside the checkpoint.
Package validation, all 98 source excerpts and exact Server/CLI/template baseline
validation also pass on that isolated source tree. The initial checks against a
nonbaseline Dex checkout and an unsupported connector-root option were rejected;
rerunning with the recorded exact baseline paths succeeded.
