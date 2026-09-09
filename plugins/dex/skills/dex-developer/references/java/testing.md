# Testing Java Dex applications

Durability claims require a real Dex Server. Unit tests are useful only for pure business helpers and codecs.

## Integration harness

Use `DexDevTestEnvironment` or the repository's `examples/java/run-integration-tests.sh`. Register only the Flows under test, allocate a temporary BlobCache, and close the environment with try-with-resources. Generate a unique Flow ID for every test so retries and terminal history cannot collide with another case.

[Pinned integration example](https://github.com/superdurable/dex/blob/4881ef2c2acd1c234e2c91320443fdffcd034f2c/sdk-java/src/test/java/io/superdurable/dex/integ/TimerTest.java)
<!-- dex-source: sdk-java/src/test/java/io/superdurable/dex/integ/TimerTest.java -->
```java
        try (DexDevTestEnvironment environment = DexDevTestEnvironment.start(
                cacheDirectory,
                WORKFLOW)) {
            final String flowId = "basic-timer-" + UUID.randomUUID();
            final long startedAt = System.nanoTime();
            environment.client().startFlow(WORKFLOW, flowId, 5);
            environment.client().waitForStepCompletion(
                    flowId,
                    StepExecutionId.of("TimerStep"),
                    Duration.ofSeconds(10));
            environment.client().waitForFlow(flowId);
```

## Required scenarios

1. Happy path: start, interact, wait for terminal status, and assert typed output.
2. Worker replacement: stop the Worker while the Flow is waiting or retrying, start a replacement with the same Registry, and prove progress resumes.
3. Retry exhaustion: make `waitFor` and `execute` fail deterministically, assert the configured recovery or terminal failure, and verify attempt-sensitive behavior.
4. Channel and RPC: publish before and after a wait registers; invoke concurrent RPCs when locks matter; verify FIFO and typed results.
5. Timer: assert it does not finish early with a tolerant upper bound. Use server waits or deadline polling, not `Thread.sleep` for convergence.
6. Terminal behavior: RPC/publish after completion must produce the expected concrete exception; a bounded `waitForFlow` timeout is not a terminal result.
7. SubFlow and cancellation: prove parent completion policy, child outcome propagation, and loser cleanup.
8. Stream: assert source and resume behavior while keeping authoritative assertions on Attributes or Flow output.

## Deadline polling

[Pinned polling helper](https://github.com/superdurable/dex/blob/4881ef2c2acd1c234e2c91320443fdffcd034f2c/sdk-java/src/test/java/io/superdurable/dex/integ/IntegrationTestWaits.java)
<!-- dex-source: sdk-java/src/test/java/io/superdurable/dex/integ/IntegrationTestWaits.java -->
```java
        final long deadline = System.nanoTime() + Duration.ofSeconds(30).toNanos();
        DexServiceException lastFailure = null;
        while (System.nanoTime() < deadline) {
            try {
                client.skipTimer(flowId, stepExecutionId, timerId);
                return;
            } catch (DexServiceException failure) {
                if (!failure.getDetail().contains(
                        "timer condition does not exist or is not pending")) {
                    throw failure;
                }
                lastFailure = failure;
                Thread.yield();
            }
        }
        throw new AssertionError("timer condition was not registered", lastFailure);
```

Keep deadlines short but non-flaky. Preserve the last failure to make timeouts diagnosable. Do not skip failures by backend or retry indefinitely.

## Commands

```bash
cd examples/java
./run-integration-tests.sh
```

For SDK work, use the repository's documented Gradle integration tasks and a real `dexcli dev`; do not substitute mocks for Worker replacement or durable waiting.
