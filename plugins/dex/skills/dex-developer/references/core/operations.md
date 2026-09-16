# Production operations

Use this guide for Dex Server deployment, production inspection, and authorized recovery. Read [testing.md](testing.md) for verification scenarios and [troubleshooting.md](troubleshooting.md) for diagnostic routing.

## Diagnostic order

1. Capture the exact Flow ID, run ID, Flow type, SDK version, and Dex Server address.
2. Check Worker application logs for handler and connectivity errors.
3. Inspect the Flow in Dex Web.
4. Run a bounded read-only inspection:

```bash
dexcli flow inspect <flow-id> --all-history
```

5. Compare the active Step, Attributes, Channel waits, Timers, and recent semantic events with the intended graph.
6. Reproduce with the smallest matching integration test.
7. Fix application code or configuration, then decide whether existing executions need recovery.

## Inspect pending Channel messages

Invoke the application's typed snapshot RPC to obtain a Channel's current FIFO values and server-assigned IDs. An ID disappears once its message is consumed or deleted. If delete or transactional move returns Channel-message-not-found, treat the local view as stale, invoke the snapshot RPC again, and let the user choose again.

Only pending Channel state is mutable through these operations. Editing a message means deleting it successfully and publishing a replacement with a new ID; it does not rewrite Flow history or application conversation Attributes.

Use a transactional RPC when deletion must commit atomically with a replacement publication or other Flow-state writes. Without transactional execution, a missing deletion may be a no-op while other effects commit; reconcile from a fresh list.

For an application queue UI, prefer one application snapshot RPC that returns durable conversation state, description, and loaded pending queues together. Refresh that snapshot after mutations and live events, on focus or reconnect, and periodically at low frequency. Keep optimistic items only as a short bridge; the snapshot is canonical.

Use **dexcli flow search**, **summary**, **state**, and **history** for narrower JSON output. Use **--no-hydrate** when payload contents are unnecessary or sensitive.

## Deploy Dex Server components

The `dex-server` image starts Web, API, and Interpreter in one OS process by default. It serves FlowService gRPC on port 8801 and Dex Web HTTP on port 8802.

Use `dex-server start --services <selection>` to scale components independently. The selection must be a nonempty comma-separated combination of `web`, `api`, and `interpreter`:

```bash
dex-server start --services web
dex-server start --services api
dex-server start --services interpreter
dex-server start --services web,api
```

Web-only does not initialize storage, Temporal, Cadence, the index synchronizer, or the Interpreter. Configure its remote API target in YAML:

```yaml
web:
  bindAddress: 0.0.0.0
  port: 8802
  flowServiceTarget: dex-api:8801
  flowRenderingDirectory: ""
```

When `web.flowServiceTarget` is empty, Web connects to `localhost:<api.port>`. The connection uses plaintext gRPC and `api.grpcMaxMessageBytes`. Put TLS, authentication, and network policy at the deployment boundary.

`/healthz` reports Web process liveness, not upstream API readiness. Web starts while FlowService is unavailable; `/api/*` returns the existing mapped gRPC error until the API recovers.

For Interpreter-only deployments, point `interpreter.interpreterActivityConfig.internalServiceTarget` at the API service. Scale Web, API, and Interpreter replicas according to HTTP traffic, FlowService traffic, and execution load respectively.

```yaml
interpreter:
  interpreterActivityConfig:
    internalServiceTarget: dex-api:8801
```

API and Interpreter replicas must use the same intended Temporal namespace or Cadence domain and compatible production storage configuration.

### Temporal Cloud attribute indexes

Temporal Cloud API-key clients cannot call the Operator Service methods that
discover and create Search Attributes. Provision the following Dex system
indexes through the Temporal Cloud control plane before starting Dex:

- `FlowType`: Keyword
- `DexParentFlowID`: Keyword
- `ActiveStepTypes`: KeywordList

Provision every indexed application Attribute before its Worker starts. Then
configure every Dex Server process that uses the namespace:

```yaml
interpreter:
  attributeIndexesManagedExternally: true
```

This mode validates application declarations but deliberately does not discover,
create, or verify indexes. A missing or incorrectly typed index therefore fails
when Temporal first uses it; treat Cloud provisioning and Worker startup as one
deployment contract.

When multiple Server processes use Streams, configure a shared Redis 7+ backend. The in-memory backend is only for one process:

```yaml
streamStore:
  backend: redis
  redisURL: redis://redis:6379/0
```

Configure Redis with `noeviction` so capacity pressure becomes a visible Stream write failure. If Blob Store is enabled, use the same durable object-store configuration across API and Interpreter replicas; do not rely on pod-local blob directories.

Blob Store keeps payloads through 100 bytes inline by default and offloads from 101 bytes. Keep the storage ID short because it appears in every durable reference; prefer a name such as `p1` over `production1`. A reference such as `p1|260913/ab3de7kp2x` uses a six-digit UTC date and a deterministic lowercase Base36 object ID. It omits the Flow ID and encoding. The Server derives the Flow-owned physical path from trusted context, and Object Blobs store the complete EncodedObject. `objectIdLength` defaults to 10; zero selects that default, negative values are invalid, and any positive length is accepted. Every Server sharing a namespace must use the same immutable value. Use 12 or 16 for unusually high per-Flow daily object counts. Values above 50 only add leading zero padding because the ID derives from SHA-256. Readers accept any nonempty lowercase Base36 object ID. Application code must treat references as opaque.

Successful ASYNC local Step input snapshots are disabled by default. Enable `blobStore.asyncStepInputSnapshotsEnabled` only when semantic history must retain the exact inputs sent to those methods. The setting is independent of the payload offload threshold and does not affect Flow execution, retry, or recovery. When disabled, no snapshot objects are written and the corresponding semantic-history inputs are unavailable. SYNC and regular-fallback inputs remain available from backend history.

## Safe recovery

Diagnosis is read-only by default. Stop, time travel, publish, invoke, skip a Timer, or mutate Attributes only when the user asks to change the Flow.

Before a mutation:

- resolve the current exact run
- explain the expected state change
- use an application Flow RPC or an explicit dexcli operation
- satisfy any explicit confirmation flag
- re-inspect the Flow afterward

Time travel is appropriate after deploying a code fix when replaying from a safe Step boundary will not duplicate an unprotected side effect. If that cannot be established, design an explicit recovery or compensation Step instead.

When a durable-history bug has already failed a Flow, validate the fix against that
same history when safe:

1. Deploy or restart the Worker with the corrected code.
2. Time travel the failed Flow to the last safe execution before the failure.
3. Let Dex replay and continue with the corrected Worker.
4. Re-inspect the new run and verify the formerly failing path and durable state.

This is stronger than testing only a new Flow because it exercises recovery from the
actual recorded history. Do not cross an external side effect unless it is idempotent,
compensated, or explicitly safe to repeat.

Sources:

- Dex CLI: https://docs.superdurable.io/references/cli
- Application operations: https://docs.superdurable.io/production/application-operations
- Versioning: https://docs.superdurable.io/production/application-operations#versioning-flow-code
