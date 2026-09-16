# Python gotchas

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

Use the pinned [typecheck contracts](https://github.com/superdurable/dex/blob/6ac5c0afe3f7c94e89d7885f5905b08aa3b8cbb1/sdk-python/tests/typecheck_contracts.py) and runnable examples rather than remembered names.
