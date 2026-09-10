# Go gotchas

- Define Attributes, Channels, Streams, and maps once at package scope; definitions carry identity.
- Register every Step emitted by `GoTo`/`MovementOf`, and register both parent and child Flows.
- Use `StepDefaultsNoWaitFor[T]` only for a true no-wait Step.
- Return every Context state, heartbeat, and Stream error.
- Do not coordinate durable work with process-local mutexes, goroutines, or maps.
- Put durable time in WaitFor; `time.Sleep` inside Execute occupies an attempt.
- Preserve omitted versus explicit zero in pointer-valued options.
- `dex.None` is nil-only; pass `nil`, not an invented empty payload.
- Graceful and force terminal decisions have different parallel/cancellation semantics.
- Give Client operations deadlines; long-poll expiry is not Flow failure.
- Validate map instance names: non-empty and no `/`.
- Keep schema/Flow packages below registry composition to avoid import cycles; inject late Client providers.

Prefer pinned [compile contracts](https://github.com/superdurable/dex/blob/ffe799a3bc22b373e8c952f4bb9eb79cc302bc34/sdk-go/dex/contracts_test.go) and runnable examples over remembered names.
