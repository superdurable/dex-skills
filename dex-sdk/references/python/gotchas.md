# Python gotchas

## Invocation contracts

Match each Client start value to the registered starting Step's input and
codec. Use `Step[None]` and `None` when there is no input; do not replace a required typed payload with `None` or an empty dictionary.

Step Stream writes and invocation-managed buffered writers belong to Step
WaitFor and Execute, including when called through helpers. RPC and Flow
timeout handlers should publish a Channel message or schedule a Step instead.
Select map values and pending Channel messages in the options of the method
that reads them; schema registration and locks do not load state. See the
[shared primitive rules](../core/primitives.md).

- The default Flow and Step types are the class names. Name each Flow class after its domain, such as `ApprovalFlow`, never just `Flow`; the module does not separate two classes with the same name.
- Do not confuse a sync generator Step with an async coroutine: generators yield `StepOutput`; coroutines await heartbeat and return a decision.
- Do not make an async generator for Execute unless the selected SDK explicitly supports it.
- Stream `write` in an async handler is synchronous at this baseline; `context.heartbeat` is awaited.
- Define schema at module scope and return the same Step instances created by the Flow.
- Register every reachable Step and both parent/child Flows.
- Do not run sync Client calls on the event loop thread.
- `asyncio.sleep` inside Execute is not a durable Timer; use it only for in-attempt work.
- Process globals, locks, tasks, and caches are lost on Worker replacement.
- Do not swallow `CancelledError`, Context output, or typed Dex exceptions.
- Avoid mutable default payload fields; use dataclass factories.
- Concrete value types beat `Any` for codec safety.
- Map instance names are non-empty and contain no `/`.
- Long-poll timeout is not Flow failure.
- Graceful and force terminal decisions have different branch/cancellation behavior.
- Temporal Cloud API-key deployments require externally provisioned indexes and `attributeIndexesManagedExternally: true`.

Use the pinned [typecheck contracts](https://github.com/superdurable/dex/blob/sdk-go/v1.5.0/sdk-python/tests/typecheck_contracts.py) and runnable examples rather than remembered names.
