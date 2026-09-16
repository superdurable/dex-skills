# Advanced Java features

## Selective loading and transactions

Use `StepOptions` and `@RPC` load declarations to request only the AttributeMap instances and pending Channels a handler reads. Selective loading is a correctness boundary: an unselected read throws. Combine Attribute locks with transactional RPC execution when multiple durable mutations must commit atomically.

## Heartbeat and buffered Stream progress

[Pinned buffered Stream source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/java/src/main/java/io/superdurable/dex/primitives/stream/StreamFlow.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/primitives/stream/StreamFlow.java -->
```java
        public StepDecision execute(final Context context, final String input) {
            final BufferedTextStream writer = BufferedTextStream.create(context, progress);
            writer.write("Rendering preview for " + input);
            writer.write("Preview ready for " + input);
            return StepDecision.gracefulComplete("Rendered " + input);
        }
```

Create one buffered writer per invocation. Flush/finalization occurs with handler completion; retries do not reconstruct unsent text. Keep a separate durable Attribute for authoritative progress.

## Step-execution locals

`setStepExecutionLocal` passes process-local data from `waitFor` to `execute` for the same Step execution. It is not durable across Worker replacement. Use it only as an optimization; reconstruct from durable input/state when absent.

## Timeout handlers

Override `Flow.handleTimeout` and select handler timeout policy only when the business needs a final notification, compensation, or explicit outcome. Give the handler its own retries and loads. Its recovery target must be a registered `Step<Void>` and can inspect `Context.getRecoveryError()`.

[Pinned timeout start source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/java/src/main/java/io/superdurable/dex/patterns/timeout/TimeoutController.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/patterns/timeout/TimeoutController.java -->
```java
                StartFlowOptions.newBuilder()
                        .timeout(Duration.ofMinutes(1))
                        .timeoutPolicy(FlowTimeoutPolicy.HANDLER)
                        .timeoutHandlerOptions(FlowTimeoutHandlerOptions.newBuilder()
                                .methodTimeout(Duration.ofSeconds(30))
                                .retry(RetryPolicy.newBuilder().maximumAttempts(3).build())
                                .build())
                        .build());
```

Use `AttributeLock.of(attribute)` for handler locks. Do not pass an Attribute directly to `addLock`.

[Pinned timeout option source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-java/src/test/java/io/superdurable/dex/WorkerServiceIntegrationTest.java)
<!-- dex-source: sdk-java/src/test/java/io/superdurable/dex/WorkerServiceIntegrationTest.java -->
```java
        final FlowTimeoutHandlerOptions timeoutOptions =
                FlowTimeoutHandlerOptions.newBuilder()
                        .methodTimeout(Duration.ofSeconds(10))
                        .heartbeatTimeout(Duration.ofSeconds(5))
                        .retry(RetryPolicy.newBuilder().maximumAttempts(3).build())
                        .durability(StepDurability.ASYNC)
                        .addLock(AttributeLock.of(status))
                        .addLoadAttributeMap(attributes)
                        .addLoadAttributeMapInstance(attributes, "tenant-a")
                        .addLoadChannel(commands)
                        .addLoadChannelMap(channels)
                        .addLoadChannelMapInstance(channels, "tenant-a")
                        .onFailureProceedTo(TimeoutRecoveryStep.class)
                        .build();
```

## Cancellation selectors

Use `withCancelingSiblingSteps` for branches created by the same predecessor and `withCancelingSteps` for all executions of a Step type. Cancellation applies after the successful decision and excludes Steps created by that same decision. Make target handlers interruption-aware and their effects idempotent.

## Async durability

Choose Step durability from workload semantics. Async execution can optimize short handlers before falling back, but shares the logical retry budget. Method timeout and heartbeat behavior can differ between phases; verify the installed SDK docs and test Worker replacement.

## BlobCache and Attribute Store

Reuse the process-level BlobCache. Opt only queryable latest-state Attributes into configured Stores. The projection is not a transactional database view and must not control a Flow decision.
