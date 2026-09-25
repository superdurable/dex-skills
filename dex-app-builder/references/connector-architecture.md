# Dex Connector Architecture v0

Dex Connector is an open-source full-stack integration layer for Dex ecosystem process applications and durable agents. It is not a generic API wrapper or a node-based automation library.

Version 0 supports Go plus the Dex SDK on the backend and React TypeScript for optional UI.

## Capability model

A connector may expose five capabilities:

- **Auth**: authorize and identify a logical connection.
- **Trigger**: translate an external event into a provider-neutral typed event.
- **Query**: read external state from a Step or agent tool.
- **Mutation**: change external state with idempotency and recovery.
- **UI**: reusable integration-aware React components.

Describe capabilities in a machine-readable `connector.yaml` catalog. Agents inspect the catalog before inventing integration code.

## Runtime boundary

Credentials belong to Connector Runtime, never Flow state, IDs, logs, browser code, or generated values. A Flow stores a logical connection ID and domain correlation data.

Every operation-specific factory in a configurable Go Flow also declares a static `ConnectionName`. It must match the generated Connection's runtime name. Dex Web uses connector ID plus connection name as the local identity and blocks writes when one identity resolves to different module versions.

A Connector Step emits only the current Query or Mutation result. Generated aliases such as `ListThreadMessagesResult` and `PostThreadReplyResult` are non-recursive aliases of `sdkgo.QueryResult` or `sdkgo.MutationResult`. `BuildOperationInput` maps the current application Step input into provider input, but that application input is not copied into the result. Persist domain context in an application-owned Attribute before invoking the Connector Step. Use `Annotations` only for graph group and explanation metadata.

Trigger processing verifies and normalizes the inbound event, preserves its stable provider event ID, and delivers it at least once. The connector does not classify a Trigger as Flow-start or RPC delivery.

The application supplies a `FlowIDResolver`. It chooses `NewDexFlowTriggerTarget` with a typed Flow and input builder to start a Flow, or `NewDexRPCTriggerTarget` with a typed RPC definition to invoke an existing Flow. Never route through a configurable RPC-name string.

Flow starts reuse the provider event ID as the request ID. The resolved Flow ID owns root-event deduplication. For RPC delivery, register the application's bound method with application-owned `dex.RPCOptions` and pass that method directly to the target. The application owns redelivery policy, bounded deduplication state when needed, and locks for the exact business state or effect that must commit atomically.

Query and Mutation run from `Execute`. Mutation supplies a stable idempotency key. If the result is uncertain, persist that outcome and query before retrying. Do not let Trigger source handlers mutate Dex primitives directly.

## UI and live state

Connector UI components are application components, not new Dex primitives. Browser code uses the application API or typed Flow RPCs.

Use a durable snapshot RPC for canonical state. Streams may improve live presentation but are best-effort; reconnect through the durable snapshot rather than treating retained Stream data as authoritative.

## Local development configuration

Dex Web v2 configures exact official Connector module releases only from loopback **dexcli dev** with local Flow definitions. It verifies release metadata and the Studio bundle before loading the bundle in an opaque-origin sandbox. When no bundle exists, the host renders the manifest form.

Flow Definition Graph metadata exposes each static Trigger binding even though its runner lives outside the Flow. A binding is identified by connector ID, connection name, Trigger name, and binding name. Its provider matcher belongs to that binding, not to the reusable connection.

The default store is `~/.dex/connectors/connections.json`. Use `dexcli dev --connector-config-dir DIRECTORY` to isolate a stack; Dex Web always displays the resolved absolute file path. The file contains plaintext development credentials, so never commit, upload, log, or copy it into Flow state.

Start the Go application with the path shown by Dex Web:

```bash
DEX_CONNECTOR_CONFIG_FILE="$HOME/.dex/connectors/connections.json" <your-app-command>
```

Load the store once with the Connector SDK `localconfig` package and create each generated connection with `NewLocalConnection(store, connectionName)`. Generated Trigger factories decode their named binding separately and wrap the target in a binding-specific disk inbox. A matched event is persisted before provider acknowledgement, removed after Dex accepts it, and replayed after a process restart.

Configuration is fixed at application startup. Credentials are reread for every provider call, so reauthorization takes effect without an application restart. Dex Web and application restarts preserve the JSON file. Restarting Dex Web clears only pending OAuth/PKCE exchanges, submitted client secrets, and UI sessions.

Local OAuth stores short-lived access tokens without refresh tokens. Reauthorize after expiry. Deleting a local credential removes only the file record; it does not revoke the provider grant.

## AI agents

Agents use the same typed Query and Mutation capabilities as deterministic Steps. Dex owns durable state, approval waits, retries, reconciliation, and cleanup. Connector code does not become a second workflow engine.

## Provider classification

Every interaction with an external provider uses a dedicated connector. This
includes Trigger, Query, Mutation, and reusable integration UI. The
generic HTTP connector is permitted only for an organization-controlled
internal system. Do not use it as an escape hatch for external SaaS APIs.

## Reuse and contribution

Inspect `https://github.com/superdurable/dex-connectors-library` and its
released component tags first. Reuse the latest compatible released dedicated
connector.

When no suitable connector exists, explain the gap and obtain authorization
before changing GitHub state. Fork the library from current `origin/main`,
implement the dedicated connector with its manifest, generated surface,
provider tests, and real Dex coverage, push the fork, and open an upstream pull
request for review.

The application may continue local verification against the fork through an
uncommitted `go.work` or temporary `replace`. Never commit a branch, commit
SHA, pseudo-version, or local replacement as the production dependency. Keep
the connector release as a production handoff blocker. After release, pin its
exact component tag and rerun integration and E2E coverage.

## Released Trigger examples

Use the [Slack thread approval example](https://github.com/superdurable/dex-connectors-library/tree/connectors/slack/v0.4.0/connectors/slack/examples/thread-approval) for a Socket Mode root event, thread query, typed reply RPC, and thread-reply Mutation.

Use the [Gmail thread reply example](https://github.com/superdurable/dex-connectors-library/tree/connectors/google/gmail/v0.5.0/connectors/google/gmail/examples/thread-reply) for a polled root message, message query, typed reply RPC, and email-reply Mutation. Its polling transport is a local alpha path, not a production push-delivery design.

Both examples derive one stable Flow ID from provider thread identity. They absorb root redelivery through deterministic starts, handle reply redelivery in bounded application-owned thread state, and move uncertain or rejected external writes into explicit recovery instead of blind resend.
