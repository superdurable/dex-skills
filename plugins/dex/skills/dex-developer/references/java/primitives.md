# Java primitives

Choose the primitive from the behavior the application needs, not from a preferred API.

| Primitive | Java shape | Use it for | Key constraint |
| --- | --- | --- | --- |
| Flow | `Flow<I>` | Durable application boundary | `getSteps()` and schema define one stable Flow type |
| Step | `Step<I>` | Retryable side effects or durable decisions | Concrete, non-parameterized `Class<I>` input |
| Wait | `Wait.until`, `anyOf`, `allOf`, `anyCombinationOf` | Durable readiness | `waitFor` observes; `execute` acts after readiness |
| Attribute / AttributeMap | `Attribute.define`, `AttributeMap.define` | Durable latest state | Define once and register in the schema |
| Channel / ChannelMap | `Channel.define`, `ChannelMap.define` | Durable FIFO commands/events | A satisfied condition consumes selected messages |
| RPC | `@RPC` and `RPCResult<T>` | Synchronous interaction with an active Flow | Declare loads and locks explicitly |
| Stream | `Stream.define` | Best-effort progress | Not authoritative state; clients resume with tokens |
| Timer | `Timer.byDuration`, `Timer.byTimestamp` | Durable deadlines | Timer readiness is not a Java sleep |
| SubFlow | `SubFlow.run` | Independently managed durable child work | Decide parent lifetime and cancellation explicitly |
| Client | `Client` | Start, wait, publish, invoke, search, stop | Catch concrete SDK exceptions |

## Wait composition

[Pinned wait example](https://github.com/superdurable/dex/blob/847960c61e59cd0ab2d578744965eae3b111b909/examples/java/src/main/java/io/superdurable/dex/primitives/waittypes/WaitTypesFlow.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/primitives/waittypes/WaitTypesFlow.java -->
```java
                case "any":
                    return Wait.anyOf(
                            channelA.forOne("signal"),
                            Timer.byDuration(timeout, "timeout"));
                case "all":
                    return Wait.allOf(
                            channelA.forOne("signal-a"),
                            channelB.forOne("signal-b"));
                case "combo":
                    return Wait.anyCombinationOf(
                            ConditionCombination.of(
                                    channelA.forOne("signal-a"),
                                    Timer.byDuration(timeout, "timeout")),
                            ConditionCombination.of(channelB.forOne("signal-b")));
```

Use condition IDs when code must distinguish winners, and for every condition inside `anyCombinationOf`. Read Channel results only from the current execution's `Context`.

## Durable state and locking

[Pinned Attribute example](https://github.com/superdurable/dex/blob/847960c61e59cd0ab2d578744965eae3b111b909/examples/java/src/main/java/io/superdurable/dex/primitives/attribute/AttributeFlow.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/primitives/attribute/AttributeFlow.java -->
```java
        @Override
        public StepOptions getStepOptions() {
            return StepOptions.newBuilder()
                    .addWaitForLock(AttributeLock.of(status))
                    .addWaitForLock(AttributeLock.of(progress, "payment"))
                    .addExecuteLock(AttributeLock.of(status))
                    .addExecuteLock(AttributeLock.of(progress, "payment"))
                    .build();
        }
```

Locks coordinate only Steps and RPCs that request the same lock. They do not make external calls transactional. AttributeMap and ChannelMap instance names must be stable business keys.

## Decisions and commit boundary

Return `StepDecision.goTo`, `goToMany`, `gracefulComplete`, `forceComplete`, `forceFail`, or `deadEnd` according to the intended lifecycle. Attribute writes and Channel publications are staged with the successful handler result. An exception discards that attempt's staged mutations. External side effects require idempotency because their success cannot be rolled back.

## Client interaction

Use `startFlow` for a new execution, `waitForFlow` for terminal status, `publish` for a Channel, and a typed RPC stub for RPCs. Use bounded waits at service boundaries and continue polling after a long-poll timeout. `searchFlows` is for indexed discovery, not coordination.
