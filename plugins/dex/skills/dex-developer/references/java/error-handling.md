# Java error handling

Separate three categories: application rejection, retryable Worker failure, and Client/service failure.

## Handler failures

Throw an application exception only when the current method attempt should fail. Configure `waitForRetry` and `executeRetry` separately. Use `waitForFailure(WaitForFailurePolicy.PROCEED)` to continue to Execute after WaitFor exhaustion, or `onExecuteFailureProceedTo` to select a registered recovery Step. A recovery Step reads `context.getRecoveryError()` and must itself be idempotent.

Do not catch an exception only to return success. That commits staged state and hides retry. Conversely, do not throw after an irreversible external success without an idempotency key or persisted receipt.

## Business outcomes

Use `StepDecision.forceFail(detail)` for a deliberate terminal failed outcome, `gracefulComplete(output)` when siblings may finish, and `forceComplete(output)` when the Flow must close now. Expected timeouts should be modeled through a Timer winner or `handleTimeout`, not as random exceptions.

## Client exceptions

Catch concrete classes in `io.superdurable.dex.exceptions`. `FlowNotFoundException` means a read found no execution. `FlowNotActiveException` means an RPC or mutation targeted a closed Flow. Durable Step and Attribute waits automatically reattach transport long polls with their effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeoutException` means the configured total handler budget expired; it does not mean the Flow failed. Treat authentication, connectivity, and serialization exceptions separately; do not branch on message text or diagnostic sub-status.

## Recovery checklist

- Persist the facts compensation needs before the risky side effect.
- Limit retries by attempts or duration when recovery must eventually run.
- Make recovery safe to retry and safe after partial external success.
- Preserve the original failure in logs with Flow ID, Run ID, StepExecution ID, method, and attempt.
- Test both `waitFor` and `execute` exhaustion when both are configured.
- Never use a recovery Step as a generic exception sink.

[Pinned heartbeat/cancellation source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/java/src/main/java/io/superdurable/dex/primitives/stepheartbeat/StepHeartbeatFlow.java)
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
