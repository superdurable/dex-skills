# Production operations

Use this guide after read-only diagnosis identifies a specific Flow and operation. Read [testing.md](testing.md) for verification scenarios and [troubleshooting.md](troubleshooting.md) for diagnostic routing.

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
