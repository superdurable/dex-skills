# Python handbook

Use this page first for Python. The [baseline project](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/pyproject.toml) selects `dex-python-sdk==0.6.0`; check `pyproject.toml`/lockfile and installed metadata before relying on baseline syntax.

## Runtime choice

Python has async (`AsyncClient`, `AsyncWorker`, `AsyncContext`) and sync (`Client`, `Worker`, `Context`) surfaces. Match the whole call chain. An async Step is an `async def` coroutine and awaits heartbeat/Client I/O. A synchronous streaming Step is a generator: it yields every `StepOutput` from heartbeat or Stream writes and returns `StepDecision` as the generator return value. A plain synchronous Step directly returns `StepDecision`. Do not mix these contracts.

## Setup and local run

Requires Python 3.11+ at the pinned example. Put Flows in application modules, compose instances in an app/registry module, share one Registry and BlobCache between Client and Worker, and keep HTTP handlers outside Flow classes.

```bash
dexcli dev
cd examples/python
uv sync --locked
uv run --frozen python main.py
```

Defaults use Dex `localhost:8801`, Worker `127.0.0.1:8803`, and HTTP `127.0.0.1:8080`.

## Minimal Flow

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/dex_examples/primitives/flow/example_flow.py)
<!-- dex-source: examples/python/dex_examples/primitives/flow/example_flow.py -->
```python
status = Attribute("status", str)
notify = Channel("notify", None)


class ExampleFlow(Flow[int]):
    def __init__(self) -> None:
        self.finish = FinishStep()
        self.example = ExampleStep(self.finish)

    def get_steps(self) -> StepList[int]:
        return StepList.start_step(self.example).other_steps(self.finish)

    def get_persistence_schema(self) -> PersistenceSchema:
        return PersistenceSchema.of(status, notify)
```

Instantiate Steps once per Flow object and return those same instances in `StepList`. Define persistent schema objects once at module scope.

A synchronous Step directly returns a decision:

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/dex_examples/primitives/flow/example_flow.py)
<!-- dex-source: examples/python/dex_examples/primitives/flow/example_flow.py -->
```python
class FinishStep(Step[int]):
    def execute(self, context: Context, input: int) -> StepDecision:
        status.set(context, "done")
        return graceful_complete(input + 1)
```

## Registry, Worker, Client

The async [application composition](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/dex_examples/app.py) shows Flow construction, Registry, BlobCache, AsyncClient, and AsyncWorker. The [sync example](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/sync-python/sync_examples/app.py) shows the synchronous counterpart. Inject services in constructors; use a provider for a Client needed after circular bootstrap.

## Route by task

- API/state choices: [primitives](primitives.md)
- Application shape: [patterns](patterns.md)
- Real-server tests: [testing](testing.md)
- exceptions/retry: [error handling](error-handling.md)
- codecs/maps/Streams: [data handling](data-handling.md)
- histories/progress: [observability](observability.md)
- open-Flow upgrades: [versioning](versioning.md)
- Python traps: [gotchas](gotchas.md)
- locks/loading/heartbeat/cancellation: [advanced features](advanced-features.md)

## Completion checklist

Verify all Steps and persistent definitions are registered, async/sync contracts are consistent, Context outputs/errors are propagated, Client awaits have deadlines, tests use unique IDs and real Dex, and no application code depends on Server internals.
