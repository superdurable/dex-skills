# Advanced Rust features

Load this page only after the Flow model and basic primitives are settled.

## Timeout handlers

A Flow may return a `FlowTimeoutHandler<Self>`. The handler is one retryable logical execution and returns a normal `StepDecision`. Start/SubFlow options select handler policy and can configure handler retries, locks, and selective loads. Keep the handler bounded; it runs because the original deadline has already expired.

[Runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/primitives/flow/flow.rs)
<!-- dex-source: examples/rust/src/primitives/flow/flow.rs -->
```rust
    fn timeout_handler(&self) -> Option<FlowTimeoutHandler<Self>> {
        Some(Self::handle_timeout)
    }
```

Use `force_complete` only if the timed-out outcome is a valid result; use `force_fail` when the deadline invalidates the operation. Persist any status needed by operators before returning.

## Cancellation-aware execution

Dex cancellation becomes observable through `Context::is_cancelled`. Long-running Execute loops should check it between bounded units of work and heartbeat progress. Cancellation is cooperative at the application boundary: blocking a single call indefinitely prevents timely observation.

For interruptible orchestration, store the interrupt request in an Attribute through an RPC, have concurrent Steps read it at safe points, and choose a deliberate graceful or forced terminal decision. See the runnable [Interruptible Flow](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/patterns/interruptible/flow.rs).

## Buffered Stream durability

`buffered_text` and `buffered_text_with_options` emit progressive text without blocking for each frame's storage acknowledgment. The buffer interval and soft byte threshold trade latency for overhead. Check handler cancellation and always propagate writer errors. Use durable Attributes or a terminal result for state that must be committed before the Step succeeds.

## Selective loading for large state

`StepOptions` offers separate WaitFor and Execute loads. `Rpc` and timeout handler options have their own loads. Prefer one map instance or ChannelMap instance when possible. This keeps Worker payloads bounded and makes data dependencies visible in the definition.

## Atomic updates

Use Attribute locks around read-modify-write invariants. Combine `.lock(...)` calls when several values must change together. Use `Rpc::is_transactional()` when Channel operations need an atomic boundary without an Attribute lock. Test conflict behavior as a typed Client error.

## Step-specific option overrides

A transition may use `StepMovement::to_with_options` to override the target execution without changing the Step's global defaults. Reserve this for call-site-specific timeout or retry semantics; if every transition needs the override, put it in `Step::options`.

## Waiting for durable acceptance

`Client::wait_for_step_completion` lets a controller wait until a selected Step reaches its defined completion, then return while background branches continue. The server derives a stable namespaced Request ID from the Step execution when options omit one. The optional total handler budget defaults to an infinite wait. The Client reattaches transport long polls with the effective ID, and the server advances to the next `-N` generation after a completed handler timeout. This is useful when an API needs a durable acceptance point rather than full Flow completion. The runnable [Wait for Step completion pattern](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/patterns/wait_for_step_completion/flow.rs) persists the request before launching background work.

## Attribute Store entity projection

Attributes marked for synchronization can project a long-lived entity Flow into an Attribute Store. Configure the store on the Flow and use RPCs as the mutation boundary. The runnable [Entity Store pattern](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/rust/src/patterns/entity_store/flow.rs) covers typed profile fields and read/update/clear RPCs.

## Feature gaps

At the pinned baseline, the Rust examples do not provide a language-specific AI-agent framework integration or resource-control example. Use core AI-agent guidance plus Rust primitives, and mark framework-specific code as application-owned. Do not manufacture SDK helpers based on another language.
