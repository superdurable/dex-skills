# Go primitives

Read core primitive semantics first. This page supplies Go API shapes at the pinned baseline.

## Flow, Step, and decisions

A Flow implements `dex.Flow`; embedding `dex.FlowDefaults` supplies optional behavior. Register the start Step with `dex.DefineStartStep` and every reachable Step with `dex.DefineStep`. Embed `dex.StepDefaultsNoWaitFor[T]` when there is no WaitFor; otherwise implement both methods.

[Pinned runnable source](https://github.com/superdurable/dex/blob/acdf5bedffa738db33d3f50ed543d8eb6c05f441/examples/go/primitives/flow/workflow.go)
<!-- dex-source: examples/go/primitives/flow/workflow.go -->
```go
func (ExampleStep) WaitFor(ctx dex.Context, _ int) (*dex.Wait, error) {
	if err := Status.Set(ctx, "running"); err != nil {
		return nil, err
	}
	return dex.SkipWaitImmediately(), nil
}

func (ExampleStep) Execute(_ dex.Context, input int) (*dex.StepDecision, error) {
	return dex.GoTo(FinishStep{}, input+1), nil
}
```

Use `GoTo`, `GoToMany`, or `DeadEnd` to keep work open. Graceful completion waits for compatible active branches; force completion/failure is an explicit terminal override.

## Wait and Timer

`dex.Until(condition)` waits for one condition; `AllOf` and `AnyOf` combine conditions. Timers are durable conditions, not sleeps inside Execute.

[Pinned runnable source](https://github.com/superdurable/dex/blob/acdf5bedffa738db33d3f50ed543d8eb6c05f441/examples/go/primitives/timer/workflow.go)
<!-- dex-source: examples/go/primitives/timer/workflow.go -->
```go
func (timerStep) WaitFor(_ dex.Context, input int) (*dex.Wait, error) {
	return dex.Until(dex.Timer(time.Duration(input) * time.Second)), nil
}

func (timerStep) Execute(_ dex.Context, _ int) (*dex.StepDecision, error) {
	return dex.GracefulComplete("timer-fired"), nil
}
```

## Attribute and AttributeMap

Define typed state at package scope with `DefineAttribute[T]` or `DefineAttributeMap[T]` and register it in `PersistenceSchema`. Reads/writes use `dex.Context` and return errors. AttributeMap instances partition one schema definition; selectively load exact instances when handlers do not receive the whole map. Index only query fields. Use an Attribute Store only when state must be queryable outside an invocation.

## Channel and ChannelMap

Channels are durable queues. `ForOne` and `ForN` create conditions; after firing, read condition results and delete/move messages deliberately. ChannelMap separates queues by validated instance name. External producers use Client; Flow-local RPCs publish through context.

[Pinned runnable source](https://github.com/superdurable/dex/blob/acdf5bedffa738db33d3f50ed543d8eb6c05f441/examples/go/primitives/channel/workflow.go)
<!-- dex-source: examples/go/primitives/channel/workflow.go -->
```go
func (channelWaitStep) WaitFor(_ dex.Context, input int) (*dex.Wait, error) {
	return dex.AnyOf(
		Approval.ForOne(),
		dex.Timer(time.Duration(input)*time.Second),
	), nil
}
```

## RPC

An exported Flow method shaped `(dex.Context, Input) (*dex.RPCResult[Output], error)` is a Worker RPC. Keep it short and lock conflicting Attributes. RPC results may request supported movements, publishing, or cancellation; never emulate transactions with process-local locks.

## Stream

Define a Stream with a byte limit and register it. A Step writes ordered progress; consumers resume from the Client token. A Stream is a feed, not authoritative state.

[Pinned runnable source](https://github.com/superdurable/dex/blob/acdf5bedffa738db33d3f50ed543d8eb6c05f441/examples/go/primitives/stream/workflow.go)
<!-- dex-source: examples/go/primitives/stream/workflow.go -->
```go
var Progress = dex.DefineStream[string]("Progress", 10<<20)

type StreamFlow struct {
	dex.FlowDefaults
}
```

## SubFlow and Client

`dex.SubFlow(child, input)` is a parent-owned Wait condition. Register parent and child, and explicitly model what parent completion means for unfinished children. Client owns external start, wait, stop, Channel, RPC, Stream, Attribute, history, search, config, timer, and reset operations. Always pass a bounded context and match typed errors with `errors.As`.

## Selection rule

Use Attribute for current state, Channel for queued intent, RPC for synchronous mutation/snapshot, Stream for incremental output, Timer for durable time, and SubFlow for an independently identified durable child.
