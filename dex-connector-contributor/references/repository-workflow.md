# Repository workflow

Use the official `superdurable/dex-connectors-library` repository. Begin from
the latest fetched `origin/main`, read its `AGENTS.md`, preserve unrelated user
files, and use an isolated `codex/` branch or managed worktree.

## Repository boundaries

- Keep the shared Go SDK in `sdkgo`.
- Keep every connector in its own Go module.
- Group a company's connectors below `connectors/<company>/...`.
- Make the first directory below `connectors/` equal `metadata.company`'s
  normalized company identity and provide its `logo.svg`.
- Give every connector its own `go.mod`, README, `connector.yaml`, generated Go
  file, provider tests, and any UI package.
- Register a connector directory in the sorted root `connectors.yaml` only when
  that directory is added, moved, or removed. A version-only change does not
  alter the registry.

## Manifest-first implementation

Treat `connector.yaml` as the release and code-generation source of truth for:

- company metadata and `metadata.version`;
- configuration and generated `Config`;
- auth fields and generated `Credentials`;
- Trigger, Query, Mutation, branch, retry, and execution definitions;
- operation-specific Step factories and defaults;
- Studio setup, commands, UI units, ports, and generated constants.

Run `connectorctl generate` after the manifest changes. Review generated code;
do not hand-edit it. Run the corresponding `--check` target before handoff.

## Versions and release order

`metadata.version` is the connector release source of truth. Leaving it
unchanged deliberately defers a release. A declared version must equal the
latest tag or the next patch, minor, or major version; first releases use
`v0.1.0`.

SDK tags use `sdkgo/vX.Y.Z`. Connector tags use the module directory, for
example `connectors/slack/vX.Y.Z`. Pin only an exact published SDK tag in a
connector `go.mod`.

When discovery exposes an SDK contract gap:

1. develop SDK and connector together with `go.work` or a temporary local
   `replace`;
2. run the full connector verification against that local SDK;
3. remove the replacement;
4. open, merge, and release the SDK PR;
5. open a later connector PR pinned to the exact new SDK release.

Never publish a branch, pseudo-version, commit SHA, or replacement. Before
release, test every module with `GOWORK=off`. Connector releases run after merge
to `main`; manual release runs only recover incomplete releases and catalog
deployment.

A v0 breaking release cannot be a patch. A v1+ breaking release requires a
major-version module-path migration before release. Put the exact lowercase
token `(breaking)` in the PR title or body and final commit subject for every
public breaking change.

## PR shape

Prefer one released module per PR. Use repository commit scopes:

- `sdkgo: ...`
- `connector(<name>): ...`
- `connector(<company>/<name>): ...`
- `tooling: ...`
- `docs: ...`

The PR explains the provider public API or official SDK used, capability and
failure semantics, version change, example, tests, live-test status, security
boundary, and any follow-up release dependency. Do not merge the PR on the
user's behalf unless explicitly authorized.

## Fixed immutable reference snapshot

The public examples used by this skill are validated against the immutable
`connectors/slack/v0.9.0` repository snapshot. At that snapshot the exact
published component versions are:

- Connector SDK `sdkgo/v0.8.0`;
- Slack `connectors/slack/v0.9.0`;
- Gmail `connectors/google/gmail/v0.10.0`;
- Google Sheets `connectors/google/spreadsheet/v0.7.0`.

These are reference baselines, not permission to downgrade a repository. For
new work, inspect current `origin/main` and the latest published component tag.
If a required tag is absent or its release failed, stop and report the release
blocker; never substitute a branch, pseudo-version, or commit SHA in public
guidance.
