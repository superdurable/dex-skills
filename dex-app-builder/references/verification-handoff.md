# Stage 4: integrate the Custom UI, verify, polish, and hand off

Read [build, test, and handoff](build-test-handoff.md). Run narrow checks while iterating, then the project's source gate and all requested real acceptance scenarios. Every Flow must pass FDG 2.0 JSON analysis with `valid: true`. A source gate does not prove business execution; a missing test service must not be reported as a pass.

Default application authoring produces source without integration/browser test
suites, mock providers, fixtures, or test-framework dependencies. Generate an
application test suite only when the user requests it. Source checks and every
production build remain required. A missing private Connector key leaves
configured execution pending; it does not block handoff of complete, checked
source whose connections are then configured in Dex Web. Connector-library
tests have their own scope and are not removed by this application default.

For No custom UI, verify that Dex Web Runs, Summary and Display fields, Work
Queue discovery, editable fields, and Actions cover the confirmed process, that
the application exposes no management route, and that any retained webhook
works. Remove mock-server routes, lifecycle state, mock controls, mock launch
scripts, and mock E2E from the product; do not preserve them as dormant
scaffolding.

For Custom UI, implement the Go backend and generated TypeScript client calls
against the same API contract. Do not wait for private provider credentials
before completing source. Implement the confirmed loading, validation, empty, success,
failure, retry, recovery, and terminal behavior. Exercise the configured real
journey without generating a separate test framework unless requested. Follow
a real-dependency test policy for requested tests; do not
introduce component mocks or intercepted API responses. Report a case requiring
unavailable dependencies as incomplete, separately from source readiness.
Do not create an application-level mock server. Do not create a second Go business backend, product mock routes,
or user-visible mock controls.
Mock evidence never replaces real Dex durability, Connector, or application E2E evidence.

Only after the real Dex and Connector end-to-end journey passes may the Custom
UI add images, custom icons, branding, animation, refined responsive behavior,
or other visual polish. Recheck the affected real journey and production build after polishing; this does not require adding an application test suite. Do not generate or source visual assets
before this stage.

Use a real Dex Server for waits, RPCs, Channels, retries, Worker replacement, terminal behavior, Work Queue permission history, and connector boundaries. Use deadline-based convergence rather than fixed sleeps.

## Local verification with dexcli dev

Verify on the long-lived `dexcli dev` stack started during implementation:

1. render every Flow into the stack's `--flow-rendering-dir` and confirm each
   Flow type appears in Dex Web v2 with its graph;
2. run the Worker against the Dex Server address that `dexcli dev` printed, so
   the FDG Flow and Step type names match the Worker's registrations;
3. configure each Connector connection in Dex Web **Connectors** and start the
   application with **DEX_CONNECTOR_CONFIG_FILE** set to the path Dex Web shows;
4. start Runs through the real entry point: a Connector Trigger, the
   application API, Dex Web **Start Flow** (which asks for the reachable Worker
   address in local mode), or `dexcli flow start`;
5. exercise Work Queue discovery with **Working as**, each Action and editable
   field, waits, Timers, retries and terminal outcomes;
6. diagnose with Dex Web and the bounded read-only `dexcli flow summary`,
   `dexcli flow state`, and `dexcli flow history` commands, recording the exact
   Flow IDs and Run IDs observed.

**Working as** filters work during local development; it does not
authenticate a user or grant permission.

## Package Flow definitions

Dex Web reads Flow Definition Graph JSON, not Go source. Produce it with one
project command that renders every Flow source file through
`dexcli visualize SOURCE --schema-version 2.0 --json --out DIRECTORY/<flow-name>`
and fails when any result is not `valid: true`. Do not ship a partial graph
written alongside blocking diagnostics. Regenerate the definitions after every
Flow change and after upgrading `dexcli`, because the rendered type names must
match the Worker.

A deployed Dex Web loads the same files from its Flow rendering source:
`web.flowRenderingSource: local` with `web.flowRenderingDirectory`, or
`blobstore` with an existing S3 blob storage and prefix
(`DEX_WEB_FLOW_RENDERING_*` environment variables override the YAML). To
replace definitions atomically, publish an immutable
`releases/<release-id>/` directory, verify every object, then replace the
strict `active-manifest` that names its prefix, file count, and digest. Follow
the pinned [Dex Web definition source contract](https://github.com/superdurable/dex/blob/server/v1.3.0/web/README.md#dynamic-definition-bundles);
Dex returns 503 rather than serving a changed, incomplete, or invalid bundle.

## Deployment, only when requested

The `dex-server` image starts Dex Web, API, and Interpreter in one process,
with FlowService on port 8801 and Dex Web on port 8802. Before deploying a
Worker, run `dexcli version check --server ADDRESS` against the target Server
and make the Worker's advertised target reachable from it. Run Dex Web in
`trusted-header` mode behind an authenticated reverse proxy that strips
browser-supplied trusted headers and injects the permission set, and keep port
8802 unreachable around that proxy. Configure deployed Connectors through the
Server's project Connector mode, as described in
[Connector architecture](connector-architecture.md#deployed-configuration-and-credential-boundary).
See the Dex SDK [operations reference](../../dex-sdk/references/core/operations.md)
for Server components and the Worker protocol check.

Finish with:

- confirmed business, UI-mode, permission-boundary, and connector decisions;
- implemented and verified behavior, with the Dex Web URL of the local stack;
- connector release or fork/PR status;
- exact test evidence, including observed Flow IDs;
- remaining limitations and release blockers;
- a clean, reviewable Git commit;
- the rendered FDG check result and, when deployment was requested, the
  observed Server, definition, configuration and real E2E identities.

Report only observed identities and results; never fabricate a deployment
command, URL, or success.
