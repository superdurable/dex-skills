# Examples, testing, and PR

## Connector-local example

Add a runnable example inside a new connector or when adding a major capability.
Extend an existing example when it already represents the provider journey.
Keep production package APIs separate from example-only business state.

With a Trigger, demonstrate the actual source, binding configuration, durable
pre-ack delivery, typed Flow start and/or typed RPC routing, application filter,
duplicate handling, restart replay, Query/Mutation usage, and explicit recovery
for uncertain writes.

Without a Trigger:

1. define a typed Flow that uses the operation-specific factory;
2. expose a valid static `ConnectionName` and any configuration UI;
3. generate strict FDG 2.0 with `valid: true`;
4. configure the connection in Dex Web v2;
5. select the healthy Worker and use **Start Flow** with schema-valid JSON;
6. inspect the Run through terminal completion or an explicit recovery path.

Start Flow is a local-selector development feature, not an authentication
boundary or substitute for a production Trigger.

## Verification matrix

Run narrow tests while iterating, then all applicable checks:

```bash
GOWORK=off go test -race ./...
GOWORK=off go vet ./...
npm ci
npm test
npm run build
```

Run those Go commands from every changed module. Then run the repository's
codegen, registry, catalog, and release-matrix checks; the connector's real Dex
integration target; strict FDG 2.0 analysis; `make test-dex-compat-current`;
and root `make check`.

Integration tests use a real Dex Server for Step retries, Attribute/Stream
registration, transitions, uncertainty, Trigger redelivery, RPCs, and Worker
replacement. Poll with deadlines and useful diagnostics; never use a fixed
sleep as correctness proof.

Run provider live tests only with dedicated safe credentials and bounded test
resources. Never paste credentials into a prompt, command line, fixture, log,
Flow value, or PR. If live credentials are unavailable, keep deterministic fake
provider coverage and list the exact live behavior as unverified in the PR.

## Four acceptance scenarios

1. **Operation-only connector:** the example generates valid FDG 2.0, is
   configured in Connections, and runs from Dex Web **Start Flow**.
2. **Trigger:** real Flow start and typed RPC delivery work across duplicate
   delivery and restart recovery.
3. **UI units:** manifest/codegen, Host API 0.2, provider command brokering,
   JSON Pointer composition, persistence, restart loading, and all visual states
   pass.
4. **SDK gap:** local joint verification succeeds, but the committed work is
   split into an SDK PR/release followed by an exact-version connector PR.

## PR handoff

Before publication, review the diff for generated drift, secrets, local
replacements, pseudo-versions, unrelated modules, and release version accuracy.
Create one clean commit using the repository scope. Push and open a
ready-for-review PR that includes:

- provider documentation or official SDK basis;
- public capability and stable identities;
- branches, retry, idempotency, uncertainty, Trigger acknowledgement, and UI
  security decisions that apply;
- example run evidence;
- every test command and result;
- provider live-test coverage or explicit omission;
- module version and any prerequisite SDK release.

Attach the PR to the task and use `$opr` to monitor all required CI. Fix
in-scope failures and continue until checks pass. Leave review and merge to the
repository maintainers unless the user explicitly authorizes more.
