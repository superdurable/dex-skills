# Testing durable behavior

Use a real Dex Server integration whenever behavior crosses a Worker, Client, persistence boundary, wait, retry, Timer, RPC, Stream, or SubFlow. A handler-only unit test cannot prove durable coordination.

## Minimum integration harness

Start an isolated Dex development environment, construct the same registry and payload/blob configuration used by the application, start the Worker, and use a Client to drive the Flow through public APIs. Give every test a unique Flow ID and cleanly stop owned processes.

Use deadline-based polling or the SDK's long-poll result API. Do not use a fixed sleep to guess when asynchronous state has converged.

## Required scenarios

- Start a Flow and verify typed terminal output.
- Replace or restart the Worker while the Flow is waiting, then verify continuation from durable state.
- Force a retryable Execute failure and verify retry count, heartbeat recovery, and exhausted-retry routing.
- Publish Channel and ChannelMap messages through typed Flow RPCs and verify ordering, single consumption, stale message IDs, and terminal rejection.
- Invoke read-only and mutating RPCs; for transactional RPCs, verify all effects commit or none do.
- Fire and skip Timers where supported; verify the business deadline and timeout-handler path.
- Exercise parallel branches and SubFlows with a deliberate failure and cancellation policy.
- Lose or reconnect a Stream consumer and recover canonical state through a typed snapshot RPC.
- Start with a duplicate Flow ID or request ID and assert the language SDK's typed result.
- Interact after terminal completion and assert the not-active or terminal behavior.

## Data and deployment scenarios

For large Attributes, replace the serving Worker and verify cold BlobCache hydration. For AttributeMap concurrency, race writers on the same instance and verify the lock-protected invariant. For Attribute Store synchronization, verify the Flow remains authoritative and the projection can reconcile after a transient failure.

For version changes, run an open Flow on the old Worker, deploy the new registry, and finish that same execution. A test that starts only after deployment does not prove open-Flow compatibility.

## Failure assertions

Assert the user-visible SDK failure type, final Flow status, recovery Step, and durable state. Do not merely assert that an exception occurred. When an external effect has an unknown outcome, record and test that state rather than assuming success or failure.

Read the selected language's **testing.md** for its harness, commands, and runnable sources.
