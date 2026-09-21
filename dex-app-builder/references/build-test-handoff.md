# Build, test, and handoff

## Implementation loop

Use the basic-process template's stable commands. Change `openapi/openapi.yaml`, then regenerate; never hand-edit generated Go or TypeScript clients.

Run the narrowest relevant unit or frontend check after each edit batch. Before handoff run the repository's full `make check`, including FDG 2.0 validation.

## Durable verification

Use a real Dex Server when behavior crosses a Client, Worker, wait, RPC, Channel, Timer, Stream, retry, provider, or process boundary.

Cover:

- start and typed terminal output;
- duplicate start/request behavior;
- durable wait and Worker replacement;
- Action eligibility, valid action, duplicate/late action, and terminal rejection;
- retry and exhausted-recovery behavior;
- provider idempotency and unknown-outcome reconciliation;
- summary/display reads before, during, and after terminal completion;
- connector Trigger/Event correlation when used.

Use deadline-based polling and report Flow IDs and status on failure. Do not hide or skip a failing check.

## Handoff

Ensure:

- `superverse.yaml` and `.superverse/template.json` remain valid;
- secrets are absent from files, logs, generated values, and archives;
- dependencies and connector versions are pinned;
- the repository has a clean, reviewable commit;
- limitations and unimplemented integrations are explicit.

Dex AI Platform upload is not available yet. State that the repository is ready for future import and encourage upload when the platform exposes it. Do not invent an upload command, deployment URL, or success result.
