# Python primitives

Read core semantics first; this page gives Python shapes at the pinned baseline.

## Flow, Step, Wait, decisions

Subclass `Flow[InputT]` and `Step[InputT]`. `get_steps` returns `StepList.start_step(instance).other_steps(...)`. A Step without `wait_for` executes immediately. `Wait.until`, all/any condition APIs, and `Wait.skip_immediately` control waiting. Return `go_to`, `go_to_many`, `dead_end`, graceful, or force decisions.

[Pinned runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/python/dex_examples/primitives/flow/example_flow.py)
<!-- dex-source: examples/python/dex_examples/primitives/flow/example_flow.py -->
```python
class ExampleStep(Step[int]):
    def __init__(self, finish: FinishStep) -> None:
        self.finish = finish

    def wait_for(self, context: Context, input: int) -> Wait:
        status.set(context, "running")
        return Wait.skip_immediately()

    def execute(self, context: Context, input: int) -> StepDecision:
        return go_to(FinishStep, input + 1)
```

## Attribute/AttributeMap and Channel/ChannelMap

Create `Attribute(name, value_type)` and `AttributeMap(name, value_type)` at module scope and include them in `PersistenceSchema`. Access via invocation Context. Maps partition by validated instance. Indexed definitions support search; Attribute Store sync supports external entity access.

Channels are durable queues. Conditions wait for one/N messages; after firing, inspect condition messages and delete/move them deliberately. ChannelMap gives one logical definition with independent instance queues. External publishers use Client; RPC handlers may publish through Context.

## Timer, RPC, Stream, SubFlow

Timer belongs in `wait_for` as a durable condition, never `asyncio.sleep` for durable scheduling. Decorate Flow methods with `@rpc`; type the input/output with `RPCResult[T]`, keep handlers short, and lock conflicting state.

Streams are typed feeds registered in persistence schema. In sync generator handlers, `yield` every Stream output. In async handlers, Stream writes are synchronous API calls at the pinned surface while heartbeat is awaited. Consumers resume from tokens.

[Pinned runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/python/dex_examples/primitives/stream/stream_flow.py)
<!-- dex-source: examples/python/dex_examples/primitives/stream/stream_flow.py -->
```python
class RenderPreview(Step[str]):
    def __init__(self, progress: Stream[str]) -> None:
        self.progress = progress

    async def execute(self, context: AsyncContext, input: str) -> StepDecision:
        progress = self.progress.buffered_text(context)
        progress.write(f"Rendering preview for {input}")
        progress.write(f"Preview ready for {input}")
        return graceful_complete(f"Rendered {input}")
```

`SubFlow(child, input)` is a parent Wait condition. Register both definitions and model unfinished-child behavior explicitly.

## Client

`Client` and `AsyncClient` own start/wait/stop, Channel publish, RPC, Stream read, Attributes, history, search, config, timers, and reset. Async calls must be awaited; sync calls must not run on an event loop thread. Use typed exceptions and explicit deadlines.

## Selection

Attribute = current state; Channel = queued intent; RPC = synchronous mutation/snapshot; Stream = incremental output; Timer = durable time; SubFlow = independently identified durable child.
