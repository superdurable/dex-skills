# Pattern selection

Choose the smallest tested Flow shape that matches the business requirement. Then read the selected language's **patterns.md** for exact APIs and runnable sources.

## Parallel Steps

- **Static parallelism**: the branches are known when the Flow is defined. Emit explicit independent Steps; add a join only when the business outcome requires one.
- **Dynamic parallelism**: the input determines branch count. Bound concurrency and retain a durable correlation between each input item and result.
- **Await all**: every branch matters. Decide whether one exhausted branch fails the whole operation or routes to recovery while the join waits for the remaining branches.
- **First win**: one acceptable result is enough. Make the winner durable and define cancellation or harmless completion for losers.

Use Steps when branches share one Flow identity and lifecycle. Do not turn a fixed graph into runtime fan-out solely to reduce source code.

## Parallel SubFlows

- **Basic**: child work needs its own identity or lifecycle; the parent waits for every child.
- **Short-lived parent**: drain the admitted batch and complete only when the active-child count is zero and the request Channel is atomically empty.
- **Long-lived parent**: the parent remains available to admit, observe, or coordinate children over time.
- **Wait for half**: quorum is sufficient. Define what happens to children outside the quorum.
- **Partitioning**: route work by a stable partition key so each parent owns a bounded subset.
- **Back pressure**: cap buffered requests, reject admission when full, and let a durable submitter retry with backoff.

Choose SubFlows for independent retry, scaling, ownership, or identity. State parent-completion, child reuse, cancellation, duplicate-submission, and concurrency semantics explicitly.

## Polling

- **Timer polling**: wait on a durable Timer between attempts when the cadence is business-defined.
- **Backoff polling**: let retry policy schedule attempts when polling is equivalent to retrying one operation.
- **Iteration polling**: keep iteration state durable when each pass changes inputs, cursor, or termination criteria.

Never block a Worker thread or coroutine with a local sleep. Persist the condition that ends the loop and enforce a total deadline or iteration budget.

## Durable timers

- **Cron**: calculate and persist the next schedule occurrence; handle missed or duplicated external effects idempotently.
- **Reminder**: self-loop after delivery while the durable completion condition remains false.
- **Inactivity tracking**: race a reset signal against a Timer and create a new deadline after each accepted activity.

A Timer is a durable condition, not an in-process timer. Define skip, cancellation, and late-delivery behavior.

## Failure handling

- **WaitFor recovery**: route a failure establishing the wait to a registered recovery Step.
- **Execute recovery**: route exhausted execution retries to explicit compensating or operator-visible work.
- **Manual recovery**: persist the failure and wait on a durable operator decision Channel.
- **Graceful timeout**: use a terminal timeout policy or a timeout handler that records a business outcome and performs bounded cleanup.

Compensation runs in reverse business order, is idempotent, and has its own failure route. Never catch an error only to report success.

## Channel draining

- **Internal publishing**: the Flow knows when every internal producer is finished; drain until producer completion and queue exhaustion are both durable.
- **External publishing**: use the atomic complete-if-Channels-empty decision so an external publication cannot race between the final empty check and Flow completion.

Keep accepted messages durable and define the point after which publication is rejected or redirected.

## Interruptible execution

Write interruption intent to an Attribute through an RPC and check it at bounded Step boundaries. Persist the outcome and make cleanup explicit. Do not assume cancelling a local future reverses an external side effect.

## Responsive update

- **Step completion**: wait for a selected named Step to commit when the caller needs durable acceptance before full Flow completion.
- **Attribute match**: wait for an application-owned revision Attribute to advance, then reload canonical state through a Describe or read RPC.
- **Stream**: publish low-latency progress when loss or duplication is acceptable; reload durable Attributes for canonical state.

Use Channels for durable commands, Attributes for durable state, and Streams for best-effort progress.

Initialize the revision to zero. Every Step and RPC that advances the represented state must declare the same Attribute lock, then read, increment, and write the revision inside that invocation. Do not advance it through concurrent Client Attribute writes.

Call **WaitForAttributeMatch** with greater-than and the last observed revision. The wait returns the current matched revision; use that value as the next watermark, then call the application's Describe or read RPC. A rapid `0 → 1 → 2 → 3` transition may return `3` from one wait for greater than `0`. This is coalescing, not an event stream, and it does not expose history, run IDs, or Temporal event IDs.

Request IDs are optional for both waits. Step completion derives `wait-for-step-completion:<StepExecutionID>`. Attribute matching derives `wait-for-attribute:<AttributeName><Condition>` from the exact predicate. The SDK automatically reattaches transport long polls with the effective ID, so one logical handler wait remains one accepted Temporal Update rather than creating an Update for every transport window. An explicit Request ID overrides the derived value and must identify only that logical wait.

The maximum wait time controls the accepted durable handler across reattachments and Continue-as-New. It is separate from a caller context, HTTP deadline, or transport long poll. Leave it at zero for ordinary waits: a few distinct waits on one active Flow can remain durable indefinitely, and identical logical waits reuse one Update ID. Set a positive value only when dynamic predicates, many concurrent consumers, abandoned callers, or conditions that may never match could exhaust that Flow's in-flight Update capacity. A finite expiry releases the slot. If the caller continues waiting, the server advances the derived or explicit ID through `-1`, `-2`, and later generations; each generation adds an accepted Update and history entry and may add a Temporal Cloud Action. Short values therefore trade in-flight capacity for total Update and Action growth. Temporal's current self-hosted defaults are 10 in-flight and 2,000 total Updates per Workflow Execution, but these are configurable deployment limits rather than Dex guarantees. See [Temporal's self-hosted defaults](https://docs.temporal.io/production-deployment/self-hosted-guide/defaults) and [Temporal Cloud Action accounting](https://docs.temporal.io/cloud/actions). For an intentional infinite revision loop, use the last returned revision as the next greater-than operand; the changed predicate produces a new derived Request ID.

String and Boolean Attributes support equal and not-equal. Integer and floating-point Attributes support all six comparison operators. Missing Attributes never match. Cross-type comparisons do not match. Object, bytes, null, blob-backed, non-finite floating-point, invalid operator, and invalid ordering operands fail. Attribute match waits target the current active Flow and require Temporal; Cadence returns Unimplemented.

## Entity store

Represent one entity lifecycle as a Flow, keep its current state in Attributes, mutate it through RPCs or Channels, and synchronize selected Attributes to an application-owned relational schema when external queries need them. Define optimistic concurrency, deletion, retention, and open-Flow compatibility.

## Selection checklist

- Does the Flow graph expose every success, wait, retry exhaustion, cancellation, timeout, and terminal path?
- Is every runtime-sized fan-out bounded?
- Are losing or abandoned branches safe?
- Are side effects idempotent or compensated?
- Is progress correctly classified as durable or best effort?
- Can a replacement Worker resume from durable state alone?

Sources:

- Pattern catalog: https://docs.superdurable.io/design-patterns
- Baseline runnable implementations: https://github.com/superdurable/dex/tree/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples
