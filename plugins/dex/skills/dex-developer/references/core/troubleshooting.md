# Troubleshooting

Begin with evidence and keep diagnosis read-only. Capture the Flow ID, run ID, Flow type, SDK version, Dex Server address, Worker build, and the last user-visible operation.

## Diagnostic order

1. Check application and Worker logs for registration, handler, connectivity, codec, and blob errors.
2. Inspect the Flow in Dex Web.
3. Run `dexcli flow inspect <flow-id> --all-history` for a bounded history view.
4. Compare the active Step, Conditions, Attributes, pending Channels, Timers, and recent semantic events with the intended graph.
5. Reproduce the path with the smallest real Dex Server integration test.
6. Fix code or configuration before deciding whether an open execution needs an authorized recovery operation.

Use `dexcli flow search`, `summary`, `state`, and `history` for narrower JSON. Use `--no-hydrate` when payload contents are unnecessary or sensitive.

## Failure routing

- **Worker unavailable**: verify process health, bind address, advertised target, name resolution, and the network path from Dex Server.
- **Unknown Flow, Step, RPC, or resource**: compare the Worker registry and persistence schema with the execution's stable names and deployed version.
- **Flow does not advance**: inspect the active Step's WaitFor conditions and pending Channel, Timer, or SubFlow state.
- **Repeated side effect**: inspect attempts and heartbeat checkpoints; make Execute idempotent or add compensation.
- **Failure after Worker replacement**: look for in-memory correctness state, incompatible codecs, unregistered old Step types, or changed schemas.
- **Large payload or hydration failure**: verify Client and Worker blob configuration, cache permissions, and matching codecs.
- **Lost progress**: determine whether the UI treated a best-effort Stream as durable state.
- **Stale queue mutation**: reload pending Channel messages; a consumed or deleted message ID cannot be reused.
- **Closed Flow interaction**: handle the language SDK's typed terminal/not-active result at the application boundary.

## Error classification

Classify a failure at the narrowest boundary with enough context to decide its meaning:

- **Business outcome**: an expected rejection, conflict, or terminal domain decision.
- **Dex or provider failure**: a typed service, transport, authentication, or availability error that policy may retry or translate.
- **Local defect**: invalid input handling, incompatible definitions, serialization, or programming errors that must remain visible.

Normal application logic catches only concrete SDK errors whose outcomes it can decide. Do not enumerate every Client failure merely to turn them all into the same retryable response; leave an unclassified failure to ordinary server-error handling unless the boundary can prove it is retryable. A narrow query-first reconciliation boundary may handle the documented concrete remote failures only when each one leaves the same mutation outcome uncertain. Use a named status or sub-status only when the SDK intentionally has no more specific concrete error; never branch on human-readable detail or raw numeric codes. Never catch a language's broad runtime or exception base for service-error translation.

The public error shape is language-specific. Python and TypeScript expose a remote-only service-error base; Go concrete remote errors unwrap to `*ServiceError`; Java intentionally has no public common service base; Rust uses one `SdkError` enum for both service-backed and local failures. Never copy a catch pattern between SDKs without checking the selected language page and installed version.

After an ambiguous provider or Client mutation, query the authoritative remote or domain state before repeating it. Bound retries and keep the repeated mutation idempotent.

## Closed-Flow races

A typed terminal or not-active error proves that the attempted interaction had no active target. It does not prove that the requested work succeeded. First reconcile from already loaded authoritative domain state and operation invariants. Re-inspect the Flow only when the outcome depends on distinguishing running, successfully completed, other terminal, and missing states and that distinction is not otherwise available. Do not spend a status call when every possible state has the same idempotent outcome.

A completed child may satisfy an idempotent cleanup only when successful completion guarantees the requested condition. An unsuccessful terminal or missing child should become an explicit domain failure or unknown outcome; do not retry a terminal fact indefinitely. A bounded wait that returns a running snapshot is still nonterminal.

## Best-effort output and fast closure

When a Stream or progress write is explicitly best effort, select only service-backed failures using the language SDK's public model because the side channel deliberately treats those failures as lossy. This means the remote-only base in Python or TypeScript, `errors.As` to Go's `*ServiceError`, Java's concrete request fallback, or Rust's service-backed variant for that operation. Log sanitized identity and phase metadata and continue the business Flow. Let local definition, validation, serialization, and programming failures surface. Retained Stream data is never the authoritative record of business completion.

If an API must return the first admission decision after a Flow can close quickly, persist that decision immutably in an authoritative domain record or projection. Do not make a late RPC to a possibly closed Flow the only source of admission correctness.

## Recovery boundary

Do not stop, time travel, publish, invoke, edit, delete, or skip a Timer during diagnosis. If the user authorizes recovery, read [operations.md](operations.md), resolve the current run, explain the expected change, perform one public operation, and re-inspect.

Read the selected language's **error-handling.md**, **observability.md**, and **gotchas.md** for concrete SDK behavior.
