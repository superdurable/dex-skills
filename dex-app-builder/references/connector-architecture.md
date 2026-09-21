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

Trigger processing verifies and normalizes the inbound event, resolves the connection, derives a stable start request and Flow ID, and starts one new Flow.

Query and Action run from `Execute`. Action supplies a stable idempotency key. If the mutation result is unknown, persist that outcome and query before retrying.

Event processing verifies and normalizes the event, resolves correlation to an existing Flow, and invokes a typed RPC. The RPC may publish to a Channel or ChannelMap. Do not let webhook handlers mutate Dex primitives directly.

## UI and live state

Connector UI components are application components, not new Dex primitives. Browser code uses the application API or typed Flow RPCs.

Use a durable snapshot RPC for canonical state. Streams may improve live presentation but are best-effort; reconnect through the durable snapshot rather than treating retained Stream data as authoritative.

## AI agents

Agents use the same typed Query and Action capabilities as deterministic Steps. Dex owns durable state, approval waits, retries, reconciliation, and cleanup. Connector code does not become a second workflow engine.

## Reuse and contribution

Inspect `https://github.com/superdurable/dex-connectors-library` first. Reuse a compatible released connector. When no implementation exists, add an application-local adapter behind the intended connector port.

A library contribution is a separate repository mutation and requires explicit user authorization. Keep the local adapter until the connector is released; then pin the release, replace the adapter, and rerun real integration and E2E coverage.
