# Build, test, and handoff

## Implementation loop

Use the basic-process template's stable commands. Change `openapi/openapi.yaml`, then regenerate; never hand-edit generated Go or TypeScript clients.

For **No custom UI**, reduce OpenAPI to `GetApplicationInfo` plus confirmed integration ingress, regenerate both clients, and remove process-management routes and mock lifecycle code. Verify the Hello World page through the generated client. Do not run a mock approval checkpoint for an inert shell.

For **Custom UI**, use `make mock` as the interaction-approval loop and run `make test-mock-e2e` after UI behavior changes. Run the narrowest relevant unit or frontend check after each edit batch. Before handoff run the repository's full `make check`, including mock E2E, real Dex integration and E2E, Worker replacement, FDG 2.0 validation, and the production build.

Treat mock results as HTTP/UI evidence only. They cannot establish Dex durability, Worker replacement, Timer, RPC, retry, or provider semantics.

## Durable verification

Use a real Dex Server when behavior crosses a Client, Worker, wait, RPC, Channel, Timer, Stream, retry, provider, or process boundary.

Cover:

- start and typed terminal output;
- duplicate start/request behavior;
- durable wait and Worker replacement;
- Action eligibility, valid action, duplicate/late action, and terminal rejection;
- role-to-permission mapping, unauthorized Action rejection, and multi-permission work discovery at the application boundary;
- concurrent Action-source writes without projection-only locks and cumulative permission history after state changes and completion;
- retry and exhausted-recovery behavior;
- provider idempotency and unknown-outcome reconciliation;
- summary/display reads before, during, and after terminal completion;
- connector Trigger Flow/RPC routing and correlation when used.

For a No custom UI application, also assert that no approval, display, status,
list, search, detail, retry, escalation, Action-proxy, or Attribute-proxy HTTP
route remains. Test each retained webhook independently from Dex Web management.

Use deadline-based polling and report Flow IDs and status on failure. Do not hide or skip a failing check.

## Handoff

Ensure:

- `superverse.yaml` and `.superverse/template.json` remain valid;
- the confirmed UI mode is recorded;
- a No custom UI shell contains no business controls or management routes;
- custom UI interactions are approved against the mock server and Mock Controls;
- secrets are absent from files, logs, generated values, and archives;
- dependencies and released connector versions are pinned;
- each configurable Connector Step has a static connection name matching its generated Connection;
- each Connector Trigger binding has a static binding name, application-owned Flow ID resolver, and typed target;
- the displayed local connection path and **DEX_CONNECTOR_CONFIG_FILE** launch command work after a Dex Web restart;
- connector fork/PR status and any release blocker are explicit;
- the repository has a clean, reviewable commit;
- limitations and unimplemented integrations are explicit.

Dex AI Platform upload is not available yet. State that the repository is ready for future import only when no connector release blocker remains. Do not invent an upload command, deployment URL, or success result.
