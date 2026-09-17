# Java error handling

Separate three categories: application rejection, retryable Worker failure, and Client/service failure.

## Handler failures

Throw an application exception only when the current method attempt should fail. Configure `waitForRetry` and `executeRetry` separately. Use `waitForFailure(WaitForFailurePolicy.PROCEED)` to continue to Execute after WaitFor exhaustion, or `onExecuteFailureProceedTo` to select a registered recovery Step. A recovery Step reads `context.getRecoveryError()` and must itself be idempotent.

Do not catch an exception only to return success. That commits staged state and hides retry. Conversely, do not throw after an irreversible external success without an idempotency key or persisted receipt.

## Business outcomes

Use `StepDecision.forceFail(detail)` for a deliberate terminal failed outcome, `gracefulComplete(output)` when siblings may finish, and `forceComplete(output)` when the Flow must close now. Expected timeouts should be modeled through a Timer winner or `handleTimeout`, not as random exceptions.

## Client exceptions

Catch concrete classes in `io.superdurable.dex.exceptions`. `FlowNotFoundException` means a read found no execution. `FlowNotActiveException` means an RPC or mutation found no active Flow because the target is missing or closed. Durable Step and Attribute waits automatically reattach transport long polls with their effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeoutException` means the configured total handler budget expired; it does not mean the Flow failed. `DexRequestException` is the concrete fallback for a request failure without a more specific public type. Its named gRPC code and Dex sub-status are diagnostic metadata; never branch on message text or raw numeric values.

Normal application code catches only the concrete exceptions whose outcomes it can decide. The Java SDK intentionally has no public catch-all exception base. Do not enumerate every Client exception merely to map every Dex failure to HTTP 503, and do not repeat that translation around every invocation. Leave `DexRequestException` to ordinary server-error handling unless a narrow query-first reconciliation boundary can prove that the failed request left a mutation outcome uncertain. Catching `RuntimeException` is not equivalent: it also hides validation, definition, serialization, and programming defects.

## Closed-Flow races

`FlowNotActiveException` says the mutation found no active target; it does not say the requested action succeeded. Catch it only where the operation contract is known. First reconcile from authoritative domain state and operation invariants. Call `describeFlow` and inspect `FlowStatus` only when an otherwise unknown terminal distinction changes the outcome:

- Treat `COMPLETED` as idempotent success only when successful completion guarantees the requested condition.
- For any other terminal status or a subsequent `FlowNotFoundException`, record or return an explicit domain failure or unknown outcome instead of retrying a terminal fact indefinitely.
- If the Flow still appears running, query its domain state before a bounded, idempotent retry.

For parent-child cleanup, a successfully completed child may let the parent continue. A missing or unsuccessfully terminal child must follow the parent's explicit cleanup-failure or cleanup-unknown route.

For an explicitly best-effort Stream write, catch only `DexRequestException`, the concrete remote failure documented by `Client.writeStream`. The side channel deliberately treats that request failure as lossy. Log sanitized Flow and phase identifiers without payloads or credentials and let the business Flow continue. Do not catch broader local failures, and never reconstruct authoritative completion state from retained Stream messages.

## Recovery checklist

- Persist the facts compensation needs before the risky side effect.
- Limit retries by attempts or duration when recovery must eventually run.
- Make recovery safe to retry and safe after partial external success.
- Preserve the original failure in logs with Flow ID, Run ID, StepExecution ID, method, and attempt.
- Test both `waitFor` and `execute` exhaustion when both are configured.
- Never use a recovery Step as a generic exception sink.

[Pinned heartbeat/cancellation source](https://github.com/superdurable/dex/blob/3e4d037f4450e78fa76e6fca157336f69984020c/examples/java/src/main/java/io/superdurable/dex/primitives/stepheartbeat/StepHeartbeatFlow.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/primitives/stepheartbeat/StepHeartbeatFlow.java -->
```java
                if (context.isCancellationRequested()) {
                    return StepDecision.deadEnd();
                }
                try {
                    Thread.sleep(Duration.ofSeconds(2).toMillis());
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return StepDecision.deadEnd();
                }
```

Cancellation is cooperative and cannot undo remote side effects. Restore the thread interrupt flag and return promptly from blocking Java handlers.
