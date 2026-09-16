# Go design patterns

Each item states its invariant and pinned runnable implementation. Preserve the invariant when adapting code.

## Parallel Steps

- **Static:** emit a fixed heterogeneous set with `GoToMany`; branches are independent. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel/static.go).
- **Dynamic:** build `[]dex.StepMovement` from input; each branch carries retry-safe input. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel/dynamic.go).
- **Await all:** workers publish once and `DeadEnd`; a coordinator waits on `Channel.ForN(count)`. Count exactly once per successful branch. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel/await_parallel.go).
- **First win:** winner completes with `CancelSiblingSteps`; losers tolerate cooperative cancellation and cannot leave uncompensated commits. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel/first_win.go).

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel/static.go)
<!-- dex-source: examples/go/patterns/parallel/static.go -->
```go
func (staticInitStep) Execute(_ dex.Context, input string) (*dex.StepDecision, error) {
	return dex.GoToMany(dex.MovementOf(workAStep{}, input), dex.MovementOf(workBStep{}, input)), nil
}
```

## Parallel SubFlows

- **Basic:** turn each request into `dex.SubFlow` and wait with `AllOf`; use only when one parent can hold the batch. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/basic_parent_flow.go).
- **Long-lived parent:** RPC checks queue size and publishes; a loop drains into children. Complete only after stop plus drain invariants. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/advanced_long_live_parent_flow.go).
- **Short-lived parent:** process a bounded batch and atomically complete only when Channels are empty. A later run uses explicit ID reuse. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/advanced_short_live_parent_flow.go).
- **Wait for half:** race children against an all-done signal and wait for `(total+1)/2`; success means quorum, not universal completion. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/wait_for_half_parent_flow.go).
- **Partitioning:** hash a stable affinity key to a fixed parent-ID set. Version the set when changing count would break affinity. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/submit_request_flow.go).
- **Back pressure:** submit through a durable Flow; rejection becomes a Step error, so retry/backoff survives Worker loss. Bound the parent queue before accepting. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/submit_request_flow.go).

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/parallel-subflows/basic_parent_flow.go)
<!-- dex-source: examples/go/patterns/parallel-subflows/basic_parent_flow.go -->
```go
func (step subFlowsStep) WaitFor(_ dex.Context, requests []string) (*dex.Wait, error) {
	conditions := make([]dex.Condition, 0, len(requests))
	for _, request := range requests {
		conditions = append(conditions, dex.SubFlow(step.exampleFlow, request))
	}
	return dex.AllOf(conditions...), nil
}
```

## Polling

- **Timer:** put delay in WaitFor and loop with `GoTo`; never sleep in Execute. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/polling/simple.go).
- **Backoff:** represent “not ready” as retryable Execute failure and use `RetryAfter` for a service hint. Bound attempts/time. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/polling/backoff.go).
- **Iteration:** carry the next page token as durable Step input and `GoTo` the same Step. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/polling/iteration.go).

## Durable Timer

- **Cron:** race Timer with trigger/skip Channels, then schedule the run and next wait in parallel. Validate interval/count. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/cron/workflow.go).
- **Reminder:** race Timer with opt-out, send at most once each iteration, and carry schedule in durable input. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/reminders/workflow.go).
- **Inactivity:** race Timer with activity; activity restarts wait, Timer moves to processing. Drain/coalesce bursts. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/inactiveness-tracker-timer/workflow.go).

## Failure handling

- **Execute recovery:** proceed to an idempotent compensating Step with enough durable input to identify the original commit. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/recovery/workflow.go).
- **WaitFor recovery:** proceed only when the recovery Step can distinguish failure and rebuild wait-side state. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/primitives/proceed-on-wait-failure/workflow.go).
- **Manual recovery:** after exhaustion, wait on durable operator decision Channels exposed through action-verb RPCs. Add durable command-ID deduplication when repeats must be idempotent. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/intervention/workflow.go).
- **Graceful timeout:** start with Handler policy and return an explicit terminal decision from `HandleTimeout`; request map/channel loads it needs. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/timeout/workflow.go).

## Draining, interruption, responsive updates, and entity state

- **Internal Channel drain:** coordinate main/side Steps, then finalize only after accepted messages drain. Keep publish/consume/delete accounting aligned. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/drain-channels/internal-drain/workflow.go).
- **External publishing drain:** accept via RPC while active and use `ForceCompleteIfChannelsEmpty` for atomic close. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/drain-channels/external-publishing/workflow.go).
- **Interruptible execution:** RPC records a signal; work uses bounded slices and checks between them. Latency is the slice duration. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/interruptible/workflow.go).
- **Responsive Step:** Client waits for one named Step boundary, not Flow completion. The server derives a stable namespaced Request ID from the Step execution when options omit one. [Runnable SDK test](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-go/dex/client_integration_test.go).
- **Responsive Attribute:** wait for a revision match, keep the returned watermark, then reload durable state. The server derives a namespaced Request ID from the Attribute predicate. [Runnable SDK test](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-go/dex/client_integration_test.go).
- **Responsive Stream:** long-poll and resume with the returned token; make consumers duplicate-tolerant. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/primitives/stream/controller.go).
- **Entity store:** use AttributeMap instances for entities, opt into Attribute Store, and lock exactly the instance an RPC mutates. [Runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/patterns/entity-store/workflow.go).

### Revision Attribute match

Initialize the integer revision Attribute to zero. Every state-changing Step or RPC must use the same Attribute lock and increment the revision inside the locked invocation. The [Job Posting Flow](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/products/job-post/workflow.go) demonstrates that mutation boundary.

Use `AttributeMatchEqual`, `AttributeMatchNotEqual`, `AttributeMatchGreaterThan`, `AttributeMatchGreaterThanOrEqual`, `AttributeMatchLessThan`, or `AttributeMatchLessThanOrEqual`. Pass a non-nil output pointer; the Client decodes the actual matched current value into it, including for non-equal operators. Singleton Attributes use `WaitForAttributeMatch`; AttributeMap entries use `WaitForAttributeMapInstanceMatch` with the instance name. `RequestID` is an optional override; the server otherwise derives it from the exact Attribute predicate. Leave `MaximumWaitTime` at zero for ordinary infinite waits. It spans transport reattachments and Continue-as-New and is separate from the caller context. Set it positive only when dynamic predicates, many consumers, abandoned callers, or conditions that may never match could consume the Flow's in-flight Update capacity. Expiry releases the slot, but continued waiting creates the next `-N` generation, another history entry, and potentially another Temporal Cloud Action. A finite expiry returns `*dex.WaitHandlerTimeoutError`. See the core responsive-update guidance for Temporal's configurable per-Workflow limits. After the wait, call the application's read RPC. The revision is a coalescing watermark, so one wait may skip intermediate values.

[Runnable durable Attribute wait](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-go/dex/client_integration_test.go)
<!-- dex-source: sdk-go/dex/client_integration_test.go -->
```go
	var matched string
	attributeOptions := WaitForAttributeOptions{}
	require.NoError(t, client.WaitForAttributeMatch(
		ctx,
		"reattach-attribute",
		clientTestStatus,
		AttributeMatchEqual("ready"),
		&matched,
		attributeOptions,
	))
	require.Equal(t, "ready", matched)
```
