# Dex Connector Architecture v0

Dex Connector is an open-source full-stack integration layer for Dex ecosystem process applications and durable agents. It is not a generic API wrapper or a node-based automation library.

Version 0 supports Go plus the Dex SDK on the backend and React TypeScript for optional UI.

## Capability model

A connector may expose six capabilities:

- **Auth**: authorize and identify a logical connection.
- **Trigger**: translate an external event into a new Flow start.
- **Query**: read external state from a Step or agent tool.
- **Action**: mutate external state with idempotency and recovery.
- **Event**: correlate an external event to an existing Flow.
- **UI**: reusable integration-aware React components.

Describe capabilities in a machine-readable `connector.yaml` catalog. Agents inspect the catalog before inventing integration code.

## Runtime boundary

Credentials belong to Connector Runtime, never Flow state, IDs, logs, browser code, or generated values. A Flow stores a logical connection ID and domain correlation data.

Every operation-specific factory in a configurable Go Flow also declares a static `ConnectionName`. It must match the generated Connection's runtime name. Dex Web uses connector ID plus connection name as the local identity and blocks writes when one identity resolves to different module versions.

Trigger processing verifies and normalizes the inbound event, resolves the connection, derives a stable start request and Flow ID, and starts one new Flow.

Query and Action run from `Execute`. Action supplies a stable idempotency key. If the mutation result is unknown, persist that outcome and query before retrying.

Event processing verifies and normalizes the event, resolves correlation to an existing Flow, and invokes a typed RPC. The RPC may publish to a Channel or ChannelMap. Do not let webhook handlers mutate Dex primitives directly.

## UI and live state

Connector UI components are application components, not new Dex primitives. Browser code uses the application API or typed Flow RPCs.

Use a durable snapshot RPC for canonical state. Streams may improve live presentation but are best-effort; reconnect through the durable snapshot rather than treating retained Stream data as authoritative.

## Local development configuration

Dex Web v2 configures exact official Connector module releases only from loopback **dexcli dev** with local Flow definitions. It verifies release metadata and the Studio bundle before loading the bundle in an opaque-origin sandbox. When no bundle exists, the host renders the manifest form.

The default store is `~/.dex/connectors/connections.json`. Use `dexcli dev --connector-config-dir DIRECTORY` to isolate a stack; Dex Web always displays the resolved absolute file path. The file contains plaintext development credentials, so never commit, upload, log, or copy it into Flow state.

Start the Go application with the path shown by Dex Web:

```bash
DEX_CONNECTOR_CONFIG_FILE="$HOME/.dex/connectors/connections.json" <your-app-command>
```

Load the store once with the Connector SDK `localconfig` package and create each generated connection with `NewLocalConnection(store, connectionName)`. Configuration is fixed at application startup. Credentials are reread for every provider call, so reauthorization takes effect without an application restart. Dex Web and application restarts preserve the JSON file. Restarting Dex Web clears only pending OAuth/PKCE exchanges, submitted client secrets, and UI sessions.

Local OAuth stores short-lived access tokens without refresh tokens. Reauthorize after expiry. Deleting a local credential removes only the file record; it does not revoke the provider grant.

## AI agents

Agents use the same typed Query and Action capabilities as deterministic Steps. Dex owns durable state, approval waits, retries, reconciliation, and cleanup. Connector code does not become a second workflow engine.

## Provider classification

Every interaction with an external provider uses a dedicated connector. This
includes Trigger, Query, Action, Event, and reusable integration UI. The
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
