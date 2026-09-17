# Python error handling

Application exceptions from `wait_for`, `execute`, RPC, and timeout handlers drive configured retry/recovery. Typed Dex exceptions describe service outcomes; `asyncio` cancellation/timeouts and transport failures describe caller/runtime conditions.

Catch precise exceptions such as `FlowNotFoundError`, `FlowNotActiveError`, `FlowAlreadyStartedError`, `LongPollTimeoutError`, `WaitHandlerTimeoutError`, `FlowUncompletedError`, `RpcLockConflictError`, and not-loaded errors. Durable Step and Attribute waits automatically reattach retryable transport long polls with their effective Request ID. The server derives a namespaced ID when none is supplied and advances its `-N` generation after a completed handler timeout. `WaitHandlerTimeoutError` means the configured total handler budget expired. Do not parse messages. Let unexpected defects retain tracebacks.

Concrete remote Client errors inherit `DexServiceError`. Local definition, not-loaded, value-mapping, argument, and programming failures do not. Catch `DexServiceError` only at a narrow boundary whose policy intentionally treats every remote Dex outcome the same; do not use it instead of concrete business outcomes. Catching `RuntimeError` is not equivalent because it also captures local SDK and application defects.

For an explicitly best-effort external `Client.write_stream` or `AsyncClient.write_stream`, suppressing `DexServiceError` is appropriate after logging sanitized identity and phase metadata. Do not suppress arbitrary exceptions. Context Stream writes inside a Step remain part of handler execution: yield or propagate their outputs and failures according to the sync or async handler contract.

Return/raise so Step retry owns retries. Use the SDK retry-after mechanism only with a meaningful delay. Never wrap durable Step work in an in-memory retry loop.

External side effects require idempotency keys derived from durable identity. Persist success or transition to recovery before acknowledging. Compensation is idempotent and carries the original commit identity.

Async APIs must be awaited. In a sync generator, yield every heartbeat/Stream `StepOutput`; swallowing one means the runtime never receives it. Do not catch `CancelledError` just to continue unsafe work.

Use automatic failure policies for deterministic recovery, operator Channels for manual choice, and the Flow timeout handler for Flow-deadline semantics. Neither a transport long-poll timeout nor a Client wait-handler timeout means the Flow failed.
