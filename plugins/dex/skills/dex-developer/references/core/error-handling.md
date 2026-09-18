# Error handling design

Use this guide before implementing a Client boundary, not only after a failure. Design the outcome of Flow starts, RPCs, cleanup, admission, waits, and external Stream writes alongside the happy path. Then read the selected language's **error-handling.md** for its actual public error model.

## Classify at the decision boundary

Classify a failure at the narrowest boundary with enough context to decide its meaning:

- **Business outcome**: an expected rejection, conflict, or terminal domain decision.
- **Dex or provider failure**: a typed service, transport, authentication, or availability error that policy may retry or translate.
- **Local defect**: invalid input handling, incompatible definitions, serialization, or programming errors that must remain visible.

Normal application logic catches only concrete SDK errors whose outcomes it can decide. Do not enumerate every Client failure merely to turn them all into the same retryable response; leave an unclassified failure to ordinary server-error handling unless the boundary can prove it is retryable. A narrow query-first reconciliation boundary may handle documented remote failures only when each one leaves the same mutation outcome uncertain. Use a named status or sub-status only when the SDK intentionally has no more specific error; never branch on human-readable detail or raw numeric codes. Never catch a language's broad runtime or exception base for service-error translation.

The public error shape is language-specific. Python, Java, and TypeScript expose a remote-only service-error base; Go concrete remote errors unwrap to `*ServiceError`; Rust uses one `SdkError` enum for both service-backed and local failures. Never copy a catch pattern between SDKs without checking the selected language page and installed version.

## Start identity and duplicate starts

Treat the Flow ID and start Request ID as separate identities. Reuse one stable Request ID only for retries of the same logical start request.

The start option that ignores an already-started error returns the existing run only when the existing execution carries the same Request ID. If the SDK still returns its typed already-started error, the Flow ID belongs to a different logical start request. Handle that as a domain conflict unless the resource-scoped Flow contract deliberately routes the new command to the existing coordinator. Do not translate it into generic service unavailability or assume the requested work already happened.

A different remote failure from `startFlow` can leave acceptance unknown. Reconcile an immutable admission record or other authoritative domain state before deciding whether to return success or retry. If no such fact exists, return an explicit retryable/unknown outcome and require the same Request ID on retry.

## Closed-Flow races

A typed terminal or not-active error proves that the attempted interaction had no active target. It does not prove that the requested work succeeded. First reconcile from already loaded authoritative domain state and operation invariants. Re-inspect the Flow only when the outcome depends on distinguishing running, successfully completed, other terminal, and missing states and that distinction is not otherwise available. Do not spend a status call when every possible state has the same idempotent outcome.

Do not assume every RPC targets only an active Flow. A query-only RPC without locks or transactional execution can read a retained terminal execution. It may succeed after closure, so use a lifecycle API when active versus terminal changes the result. If a query-path handler returns durable effects, it may run before the later Signal fails with a not-active error. Transactional, locked, and Server-forced Update paths require an active execution before the Worker handler runs.

A completed child may satisfy an idempotent cleanup only when successful completion guarantees the requested condition. An unsuccessful terminal or missing child should become an explicit domain failure or unknown outcome; do not retry a terminal fact indefinitely. A bounded wait that returns a running snapshot is still nonterminal.

## Ambiguous mutations

After an ambiguous provider or Client mutation, query the authoritative remote or domain state before repeating it. Bound retries and keep the repeated mutation idempotent. Preserve the stable request identity across every retry of the same logical mutation.

## Best-effort output and fast closure

When a Stream or progress write is explicitly best effort, select only service-backed failures using the language SDK's public model because the side channel deliberately treats those failures as lossy. This means the remote-only base in Python, Java, or TypeScript, `errors.As` to Go's `*ServiceError`, or Rust's service-backed variant for that operation. Log sanitized identity and phase metadata and continue the business Flow. Let local definition, validation, serialization, and programming failures surface. Retained Stream data is never the authoritative record of business completion.

If an API must return the first admission decision after a Flow can close quickly, persist that decision immutably in an authoritative domain record or projection. Do not make a late RPC to a possibly closed Flow the only source of admission correctness.

## Design review

- Does every caught error change a domain decision, retry policy, or boundary translation?
- Are typed conflicts handled before a remote-error fallback?
- Can an accepted mutation lose its response, and if so, what authoritative fact reconciles it?
- Are retries bounded, idempotent, and tied to one stable Request ID?
- Can a closed or missing Flow converge without an unnecessary status call?
- Does best-effort observation remain separate from authoritative business state?
- Do local definition, mapping, serialization, and programming defects remain visible?
