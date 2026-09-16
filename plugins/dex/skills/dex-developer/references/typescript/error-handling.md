# TypeScript error handling

## Worker handler failures

Throw or reject when the method attempt must fail. Configure `waitForRetry` and `executeRetry` independently and route exhausted failures with `WaitForFailure` or `ExecuteFailure`. A recovery Step reads `context.recoveryError` and must be registered in the Flow's StepList.

Do not catch and return a success decision merely to suppress retry. That commits staged mutations. External calls are outside the Dex commit, so use stable idempotency keys and compensation for ambiguous outcomes.

## Client failures

Catch exported SDK error classes such as `FlowAlreadyStartedError`, `FlowNotFoundError`, `FlowNotActiveError`, and `WaitHandlerTimeoutError`. Durable Step and Attribute waits automatically reattach transport long polls with their effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeoutError` means the configured total handler budget expired; it does not mean the Flow failed. For lower-level cases, `DexServiceError` exposes the gRPC code and diagnostic detail. Do not compare human-readable detail for normal control flow when a typed error exists.

[Pinned example error classification](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/typescript/src/service-errors.ts)
<!-- dex-source: examples/typescript/src/service-errors.ts -->
```typescript
export function isFlowAlreadyStarted(error: unknown): boolean {
  return error instanceof DexServiceError && error.code === grpcAlreadyExists;
}

export function isFlowMissingOrInactive(error: unknown): boolean {
  return error instanceof DexServiceError && error.code === grpcNotFound;
}
```

The runnable examples use code classification only where one service code intentionally combines missing and inactive outcomes. Prefer exported concrete errors in new application code.

## Async discipline

Await every Client call. If a fire-and-forget call is intentional, attach rejection handling and document ownership. Let Express/Koa/Fastify error middleware translate expected application errors; do not erase `cause`, Flow ID, or method context.

## Recovery checklist

- Bound retries so recovery can run.
- Persist compensation facts before risky effects.
- Make each effect and compensation retry-safe.
- Log Flow ID, Run ID, StepExecution ID, method, attempt, and original cause.
- Treat cancellation as a request, not proof the remote effect stopped.
- Test failure before commit, after external success, during replacement, and after terminal Flow status.
