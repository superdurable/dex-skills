# TypeScript primitives

Choose primitives from the business behavior first, then encode them with the SDK's TypeScript shapes.

| Primitive | TypeScript shape | Use it for | Key constraint |
| --- | --- | --- | --- |
| Flow | `Flow<I>` | Durable application boundary | Stable `getFlowType`, complete Step/schema registry |
| Step | `Step<I>` | Retryable work and transitions | Stable Step type and matching `Codec<I>` |
| Wait | `Wait.until`, `anyOf`, `allOf`, `anyCombinationOf` | Durable readiness | Wait is returned, never awaited as a Promise |
| Attribute / AttributeMap | `new Attribute`, `new AttributeMap` | Durable latest state | Durable name and codec are compatibility surface |
| Channel / ChannelMap | `new Channel`, `new ChannelMap` | Durable FIFO messages | Selected waits consume messages |
| RPC | `@rpc({...})` and `RPCResult<T>` | Active-Flow request/response | Codecs, loads, locks, and transaction are explicit |
| Stream | `new Stream` | Best-effort progress | Not a source of truth |
| Timer | `Timer.byDuration`, `Timer.byTimestamp` | Durable deadlines | Milliseconds are numbers; no event-loop timer survives Worker loss |
| SubFlow | `SubFlow.run` | Durable child work | Parent/child lifetime is an application decision |
| Client | Promise-returning `Client` methods | Start, wait, publish, invoke, search, stop | Await network operations and catch typed errors |

## Wait composition

[Pinned wait example](https://github.com/superdurable/dex/blob/847960c61e59cd0ab2d578744965eae3b111b909/examples/typescript/src/primitives/wait-types/wait-types-flow.ts)
<!-- dex-source: examples/typescript/src/primitives/wait-types/wait-types-flow.ts -->
```typescript
    if (input.mode === "any") {
      return Wait.anyOf(
        channelA.forOne("signal"),
        Timer.byDuration(timeoutMs, "timeout"),
      );
    }
    if (input.mode === "all") {
      return Wait.allOf(
        channelA.forOne("signal-a"),
        channelB.forOne("signal-b"),
      );
    }
```

Use condition IDs when execution must distinguish winners and for every condition inside `anyCombinationOf`. Inspect results on the current `Context`.

## Codecs and schema

Use `stringCodec`, `booleanCodec`, `int64Codec`, `doubleCodec`, `bytesCodec`, or a deliberate `jsonCodec<T>` with validation for application models. Default JSON encoding does not validate TypeScript shapes at runtime. Register every Attribute, Channel, and Stream in exactly one Flow schema.

## State, locks, and transaction

[Pinned Channel transaction example](https://github.com/superdurable/dex/blob/847960c61e59cd0ab2d578744965eae3b111b909/examples/typescript/src/primitives/channel/channel-flow.ts)
<!-- dex-source: examples/typescript/src/primitives/channel/channel-flow.ts -->
```typescript
  @rpc({ isTransactional: true, loadChannels: [queued], inputCodec: moveMessageCodec })
  public move(context: Context, message: MoveMessage): void {
    const messageToMove = queued.findPendingMessage(context, message.messageId);
    queued.delete(context, message.messageId);
    if (messageToMove !== undefined) {
      moved.publish(context, messageToMove.value);
    }
  }
```

Staged Attribute and Channel mutations commit with a successful handler result. An exception discards that attempt's mutations. Locks coordinate only handlers requesting the same lock; external effects still need idempotency.

## Decisions

Use `goTo`, `goToMany`, `gracefulComplete`, `forceComplete`, `forceFail`, `deadEnd`, and conditional completion helpers to express lifecycle. Do not encode control flow in mutable module globals. A Flow can have `StepList.empty()` or `withoutStartStep` when started work is driven by RPCs.
