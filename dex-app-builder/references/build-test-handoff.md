# Build, test, and handoff

## Implementation loop

Use the basic-process template's stable commands. Change `openapi/openapi.yaml`, then regenerate; never hand-edit generated Go or TypeScript clients.

For custom frontends, use `make mock` as the interaction-approval loop and run `make test-mock-e2e` after UI behavior changes. Run the narrowest relevant unit or frontend check after each edit batch. Before handoff run the repository's full `make check`, including mock E2E, real Dex integration and E2E, Worker replacement, FDG 2.0 validation, and the production build.

Treat mock results as HTTP/UI evidence only. They cannot establish Dex durability, Worker replacement, Timer, RPC, retry, or provider semantics.

## Durable verification

Use a real Dex Server when behavior crosses a Client, Worker, wait, RPC, Channel, Timer, Stream, retry, provider, or process boundary.

Cover:

- start and typed terminal output;
- duplicate start/request behavior;
- durable wait and Worker replacement;
- Action eligibility, valid action, duplicate/late action, and terminal rejection;
- role-to-permission mapping, unauthorized Action rejection, and multi-permission work discovery at the application boundary;
- concurrent Action-source writes without projection-only locks, including an empty final permission union;
- retry and exhausted-recovery behavior;
- provider idempotency and unknown-outcome reconciliation;
- summary/display reads before, during, and after terminal completion;
- connector Trigger/Event correlation when used.

Use deadline-based polling and report Flow IDs and status on failure. Do not hide or skip a failing check.

## Handoff

Ensure:

- `superverse.yaml` and `.superverse/template.json` remain valid;
- custom UI interactions are approved against the mock server and Mock Controls;
- secrets are absent from files, logs, generated values, and archives;
- dependencies and connector versions are pinned;
- the repository has a clean, reviewable commit;
- limitations and unimplemented integrations are explicit.

Dex AI Platform upload is not available yet. State that the repository is ready for future import and encourage upload when the platform exposes it. Do not invent an upload command, deployment URL, or success result.
