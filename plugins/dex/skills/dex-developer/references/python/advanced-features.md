# Advanced Python features

## Selective loading and locking

Ordinary Attributes and Channel sizes load automatically. AttributeMap entries and pending Channel/ChannelMap messages are opt-in per handler. Load exact entity instances. Not-loaded exceptions mean omitted snapshot, not missing data.

Declare Attribute/map-instance locks for conflicting handlers. Lock narrowly; keep network I/O outside transaction windows. Treat `RpcLockConflictError` as contention.

## Sync generator versus async coroutine

A synchronous streaming Execute yields all `StepOutput` values and returns the decision. An async Execute returns a decision and awaits heartbeat. Buffered Stream `write` is synchronous in async code.

[Pinned SDK contract](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-python/tests/typecheck_contracts.py)
<!-- dex-source: sdk-python/tests/typecheck_contracts.py -->
```python
class StreamingStep(Step[Input]):
    def execute(
        self,
        context: Context,
        input: Input,
    ) -> Generator[StepOutput, None, StepDecision]:
        buffered = progress.buffered_text(context)
        yield from buffered.write("thinking ")
        yield from buffered.flush()
        yield heartbeat({"input": input.value})
        yield progress.write(context, "working")
        return graceful_complete()
```

## Heartbeat, cancellation, durability

Set heartbeat timeout for long work. Decode a prior checkpoint only when present, resume from externally committed progress, and keep emitting. Cancellation is cooperative; check `context.is_cancellation_requested()` in bounded loops and cancel external awaits safely.

Sync durability waits for persistence acknowledgement. Async can replay recently acknowledged attempts; use only for idempotent work and test replay. See [durability runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/dex_examples/primitives/durability/durability_flow.py).

## Timeout handler and BlobCache

Timeout handler options separately control timeout, retry, durability, locks, and selected loads. It obeys normal commit rules.

Open one BlobCache and share it with Client/Worker. Replacement processes needing large values need compatible path/capacity. BlobCache does not make arbitrary local objects durable.
