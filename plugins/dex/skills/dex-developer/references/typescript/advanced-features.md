# Advanced TypeScript features

## Async handlers

Step, WaitFor, RPC, and timeout handlers may return Promises. Awaiting Client work yields the Node event loop, so the same Worker can serve the child Flow or RPC it calls. Avoid circular waits and synchronous CPU loops. Propagate `AbortSignal` to libraries that support cancellation.

## Selective loading and transactional RPCs

Use Step/RPC load options for AttributeMap instances, Channels, and ChannelMaps. Reading outside the selected scope throws. Use `isTransactional: true` when a failed Channel deletion must roll back other staged RPC mutations. Locks provide isolation only among cooperating handlers.

## Buffered Streams

[Pinned buffered Stream source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/typescript/src/primitives/stream/stream-flow.ts)
<!-- dex-source: examples/typescript/src/primitives/stream/stream-flow.ts -->
```typescript
  public async execute(context: Context, input: string): Promise<StepDecision> {
    const writer = progress.bufferedText(context, { flushIntervalMs: 500 });
    writer.write(`Rendering preview for ${input}`);
    writer.write(`Preview ready for ${input}`);
    return gracefulComplete(`Rendered ${input}`);
  }
```

Create the writer within one invocation. Buffered text flushes before the final result, but unsent data is not restored or deduplicated on retry. Keep durable status elsewhere.

## Heartbeat checkpoints

Use `AsyncContext.recordHeartbeat` with the same codec used by `getLastHeartbeatValue`. A Stream write acts as liveness but does not replace a useful checkpoint. Cancellation can arrive through the signal while an awaited operation is running.

## Timeout handlers

Implement `handleTimeout` when a soft deadline needs a business decision or compensation. Configure handler loads/retry separately. An exhausted handler can route to a registered `Step<void>` and inspect `context.recoveryError`.

## Cancellation selectors

Wrap a successful decision with `withCancelingSiblingSteps` for same-parent branches or `withCancelingSteps` for all executions of a Step type. Targets are resolved from the current snapshot; Steps created by that decision are excluded. RPCs may request Flow-wide cancellation but have no sibling lineage.

## Step-execution local data

Execution-local values pass data between `waitFor` and `execute` in one Worker process. They are not durable across replacement. Treat absence as normal and reconstruct from durable input/state.

## BlobCache and projections

Share a process-level BlobCache. Attribute Store synchronization is asynchronous latest-state projection, not a transactional read model. Model correctness inside the Flow.
