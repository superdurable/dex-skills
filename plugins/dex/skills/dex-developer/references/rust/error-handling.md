# Rust error handling

Separate handler failures from controller/client failures. A Step or RPC returns `HandlerResult<T>` and uses `HandlerError` to control retryable Worker behavior. A Client operation returns `SdkResult<T>` and exposes typed `SdkError` variants. Do not collapse either into strings before policy or HTTP mapping has examined it.

## Handler failures and retries

Return errors with `?` when a durable read or write fails. For an application failure, construct a stable error type and useful message. `HandlerError::retry_after` overrides the next retry delay for that failure; `StepOptions::execute_retry` still bounds attempts.

[Runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/primitives/custom_retry/flow.rs)
<!-- dex-source: examples/rust/src/primitives/custom_retry/flow.rs -->
```rust
    fn options(&self) -> StepOptions<Self::Input> {
        StepOptions::new().execute_retry(RetryPolicy::new().maximum_attempts(5))
    }

    fn execute(
        &self,
        context: &mut Context,
        ready_after_attempt: Self::Input,
    ) -> HandlerResult<StepDecision> {
        if i32::try_from(context.attempt()).unwrap_or(i32::MAX) < ready_after_attempt {
            return Err(HandlerError::retry_after(
                7,
                "CustomRetry",
                format!("not ready on attempt {}", context.attempt()),
            ));
        }
        Ok(StepDecision::graceful_complete(String::from("ready")))
    }
```

Make Execute side effects idempotent across attempts. Dex retries a logical method execution; a remote service may have accepted the previous call even when the Worker did not observe the response.

## WaitFor versus Execute failure

Configure retry policies for the phase that can fail. WaitFor should normally be pure durable preparation. If WaitFor exhaustion is explicitly recoverable, set `WaitForFailurePolicy::Proceed`; Execute must then check `context.wait_for_method_failed()` before selecting a recovery transition.

[Runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/primitives/proceed_on_wait_failure/flow.rs)
<!-- dex-source: examples/rust/src/primitives/proceed_on_wait_failure/flow.rs -->
```rust
    fn options(&self) -> StepOptions<Self::Input> {
        StepOptions::new()
            .wait_for_failure(WaitForFailurePolicy::Proceed)
            .wait_for_retry(RetryPolicy::new().maximum_attempts(2))
    }

    fn wait_for(&self, _context: &mut Context, _input: Self::Input) -> HandlerResult<Wait> {
        Err(HandlerError::new(
            "ProceedOnWaitFailure",
            "planned WaitFor failure",
        ))
    }
```

Never enable Proceed without a deliberate Execute branch; otherwise failed preparation is mistaken for successful readiness.

## Recovery choices

- Compensation Step: use when completed effects can be reversed deterministically.
- Manual recovery: wait on operator Channels after automatic retries exhaust.
- Graceful timeout handler: make a final bounded decision when the Flow deadline wins.
- Force fail: use when no safe continuation exists.
- Dead end: terminate only one branch; do not confuse it with failing the whole Flow.

Record recovery progress durably before triggering another non-idempotent action.

## Client errors

Match `SdkError` variants that affect external behavior, such as `FlowAlreadyStarted`, `WaitHandlerTimeout`, `RpcLockConflict`, Channel message absence, or Worker invocation failure. Durable Step and Attribute waits automatically reattach transport long polls with their effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeout` means the configured total handler budget expired; it does not mean the Flow failed. Controllers should map known conflicts and invalid requests distinctly from infrastructure failures. Preserve `source()` chains in logs. Do not retry every `SdkError`; only retry operations whose semantics and request IDs make repetition safe.

## Terminal decisions

`graceful_complete` waits for the Flow's branch semantics; `force_complete` terminates immediately; `force_fail` fails immediately. Assert the intended Flow status in integration tests. A successful method return is not evidence that buffered Stream output or unrelated sibling work has finished.
