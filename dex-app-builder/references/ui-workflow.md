# Application surface workflow

Use this after discovery identifies whether the application needs custom
process UI.

## No custom UI

Dex Web owns every process-management interaction. Adapt the template to keep:

- a non-business Hello World React page;
- the Go HTTP server and OpenAPI source;
- generated Go server interfaces and TypeScript client;
- one `GetApplicationInfo` operation used by the page;
- generation, build, and smoke-test commands.

Remove process state, management operations, Action/Attribute proxy endpoints,
dashboards, forms, mock lifecycle state, Mock Controls, fixtures, and related
tests. The shell must not present approval, display, status, list, search,
detail, retry, or escalation controls.

Retain a webhook only when it is confirmed integration ingress. An external
provider webhook belongs to its dedicated Connector Trigger. An internal
system may use the generic HTTP webhook connector.

Do not require mock approval for the inert shell. Verify that the generated
client calls `GetApplicationInfo`, the production build passes, and no
management route remains. If custom behavior is requested later, follow the
workflow below before connecting it to production.

## Custom UI

### Interaction design

Agree on:

- role-specific entry points and navigation;
- how authenticated roles become the permissions available to each entry point;
- list, detail, create, action, and completion experiences;
- which state is canonical and how stale state is refreshed;
- action eligibility and confirmation;
- required inputs, validation, empty states, loading, recoverable errors, and terminal errors;
- responsive behavior and accessibility;
- which Dex Web v2 surfaces remain available to maintainers.

Do not claim application-level UI controls provide platform RBAC. A permission selector filters work; it does not grant permission. Enforce identity-to-permission mapping at the trusted application boundary. Keep credentials and provider secrets server-side.

### Mock checkpoint

Implement the first pass in the template React TypeScript application and run `make mock`. This starts the Go in-memory mock API and Vite hot reload without a Dex Client or Worker. Use the visible Mock Controls to advance the lifecycle, emit reminders, inject one-time start/refresh/approval failures, retry recoverable errors, and reset state. Browser refresh must preserve mock state until Reset or server restart.

Drive the primary lifecycle through the mock API. Local typed fixtures remain appropriate for isolated component states, but they do not replace the runnable interaction path. Cover the happy path plus empty, loading, validation, recoverable provider-error, retry, and terminal states. Keep mock controls out of the production build experience.

Run frontend tests, `make test-mock-e2e`, and the production build. Render or open the mock when the environment supports visual inspection. Summarize the observed interactions and wait for explicit user approval.

Before approval, do not:

- treat a provisional mock interaction contract as final;
- bind components to the real Dex-backed application server;
- add Dex Client access to the browser;
- implement backend behavior inferred only from the mock.

After approval, finalize OpenAPI as the HTTP contract source, regenerate both server and browser clients, and connect the same approved interactions to the production Go/Dex backend. Browsers call the application API or typed Flow RPC boundary, never raw Dex primitives.
