# Versioning Go applications

## Check first

```bash
go list -m github.com/superdurable/dex/sdk-go
go list -m -json github.com/superdurable/dex/sdk-go
```

The selected SDK source is authoritative. Baseline snippets are evidence only for the pinned Dex commit.

## Business continuity

Apply the shared [RunID boundary](../core/versioning.md#business-identity-and-continue-as-new).
Ordinary API/RPC DTOs and effect keys use stable business IDs/FlowID and domain
revisions. Continue-As-New preserves that lifecycle; it does not reset message
sequences, pending work, cursors or UI state. Keep SDK run selectors/return values
truthful but internal; exact RunID selection is for diagnosis/history or explicit
execution recovery. Test continuity without adding a current-run lookup.

## Server protocol compatibility

The Go Worker obtains its diagnostic artifact version from Go build information. On startup it calls `GetServerInfo`, negotiates the highest common protocol, synchronizes Attribute indexes, and then binds WorkerService. A missing RPC, invalid interval, or disjoint interval fails startup before the listener opens. Upgrade a legacy Server first; stop running Workers before a breaking Server upgrade because they do not renegotiate.

## Open-Flow compatibility

An open Flow can resume on new Worker code. Preserve Flow type, reachable Step type strings, registered schemas, and decodable payloads. Do not rename a Step as a refactor. Add a new Flow/Step type for incompatible behavior and route new starts there.

Additive fields with defaults are usually safer. Removing registered Steps, changing state types, repurposing enum values, or changing retry/terminal invariants is risky.

## Rollout

Deploy a Worker able to serve old and new runs, then move traffic deliberately. Updating a process does not replace durable execution state.

[Pinned runnable source](https://github.com/superdurable/dex/blob/sdk-go/v0.13.1/examples/go/primitives/flow/controller.go)
<!-- dex-source: examples/go/primitives/flow/controller.go -->
```go
func rerouteActiveFlow(ctx context.Context, client *sdk.Client, flowID string) error {
	return client.UpdateFlowConfig(ctx, flowID, sdk.FlowConfig{
		WorkerTarget: &sdk.WorkerTarget{Address: "worker-canary:8803"},
	})
}
```

Choose ID reuse and already-started behavior as product semantics. Test active and closed prior runs. Before rollout, start representative Flows on old code, stop at durable boundaries, replace the Worker, and complete them on new code. Include maps, Channels, Timer, RPC, retry, and timeout handler.
