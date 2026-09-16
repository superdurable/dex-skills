# Go error handling

## Error layers

Application errors from WaitFor, Execute, RPC, and timeout handlers drive configured retry/recovery. Typed Client errors describe Dex outcomes. Context/transport errors describe caller cancellation or connectivity. Keep these layers distinct.

Use `errors.As` for `*dex.FlowNotFoundError`, `*dex.FlowNotActiveError`, `*dex.FlowAlreadyStartedError`, `*dex.LongPollTimeoutError`, `*dex.WaitHandlerTimeoutError`, and `*dex.FlowUncompletedError`. Durable Step and Attribute waits hide retryable transport long-poll expiry by reattaching with the effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeoutError` means the configured total handler budget expired. Keep `ServiceError.SubStatus` for diagnostics; never parse strings.

## Retry ownership

Return an error when Step options should decide retry. Use `dex.RetryAfter` only when the application knows a meaningful delay. Never add an in-memory retry loop around Step work; it disappears with the Worker and hides attempts.

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/polling/backoff.go)
<!-- dex-source: examples/go/patterns/polling/backoff.go -->
```go
	result, err := step.service.AttemptExternalAPICall("Poll for BackoffPollingFlow")
	if err != nil {
		return nil, dex.RetryAfter(time.Second, err)
	}
	return dex.GracefulComplete(result), nil
```

## Commit and recovery

Before non-idempotent external work, use an idempotency key derived from durable identity. After a successful side effect, persist the fact or move to a recovery-capable Step. A returned error permits retry from the previous boundary.

Use Execute/WaitFor failure policies for automatic recovery, operator Channels for manual recovery, and a timeout handler for Flow-deadline semantics. Compensation must be idempotent and identify the original commit.

Every Context operation can fail. Return or wrap its error; do not continue after a failed Attribute write, Channel delete, heartbeat, or Stream write as though it committed.
