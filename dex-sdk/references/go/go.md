# Go handbook

Use this page first for a Go application. It describes the application boundary and points to focused pages; always check the version selected by `go.mod` and `go.sum`.

## Version and source authority

The [baseline module](https://github.com/superdurable/dex/blob/sdk-go/v0.12.1/examples/go/go.mod) uses `github.com/superdurable/dex/sdk-go v0.10.2`. Before editing an existing project, run `go list -m github.com/superdurable/dex/sdk-go` and inspect that SDK version. If it differs from the baseline, installed source wins. Identify the inspected module-cache path, vendored path, or immutable tag/commit before presenting exact syntax. If no version-matched source is available, give only the version-independent Flow model and request that source; do not adapt baseline snippets speculatively. Pinned sources show known-good shapes, not a promise that every version has the same surface.

## Project shape and local run

Keep Flow and Step definitions in application packages, compose them in one registry package, and create one shared Registry and BlobCache for Client and Worker. Inject business services into Flow constructors. The official example layout is `products/`, `patterns/`, `primitives/`, `registry/`, `shared/`, and `cmd/server/`.

```bash
dexcli dev
cd examples/go
make bins
./dex-samples
```

Defaults use Dex at `localhost:8801`, a Worker listener at `127.0.0.1:8803`, and HTTP at `127.0.0.1:8080`. `DEX_WORKER_TARGET` is the address advertised to Dex and can differ from the bind address.

## Local Connector configuration

Official Go connectors can load the Dex Web development store with `localconfig.LoadFromEnvironment`. Create each generated connection with `NewLocalConnection(store, "connection-name")`, and set the same static `ConnectionName` on every operation-specific factory config. Start the application with **DEX_CONNECTOR_CONFIG_FILE** set to the absolute path shown by Dex Web.

Configuration is captured when the store loads. Credentials are reread for each provider call, so reauthorization does not require a restart; configuration changes do. Keep generated secret values outside Flow state and logs.

Provider-neutral Triggers run outside Steps. Give each generated Trigger factory a static binding name, then pass an application-owned target. `NewDexFlowTriggerTarget` takes the typed Flow, a stable `FlowIDResolver`, and an input builder. `NewDexRPCTriggerTarget` takes a typed RPC definition and the same identity resolver; no string RPC name is configured.

For RPC delivery, construct `TriggerRPC` from the Flow's bound method and application event handler. Register its `Definition()` with `DefaultOptions()`, include `PersistenceAttribute()` in the Flow schema, and delegate the bound method to `Handle`. This atomically deduplicates stable provider event IDs without putting business behavior in the connector.

Use the released [Slack example](https://github.com/superdurable/dex-connectors-library/tree/connectors/slack/v0.1.0/connectors/slack/examples/thread-approval) and [Gmail example](https://github.com/superdurable/dex-connectors-library/tree/connectors/google/gmail/v0.2.0/connectors/google/gmail/examples/thread-reply) as the exact integration references.

## Minimal Flow

Declare schema at package scope, embed defaults, register Step types, and return a decision from every Execute method.

[Pinned runnable source](https://github.com/superdurable/dex/blob/sdk-go/v0.12.1/examples/go/primitives/flow/workflow.go)
<!-- dex-source: examples/go/primitives/flow/workflow.go -->
```go
var (
	Status = dex.DefineAttribute[string]("status")
	Notify = dex.DefineChannel[dex.None]("notify")
)

type ExampleFlow struct {
	dex.FlowDefaults
}

func NewExampleFlow() *ExampleFlow {
	return &ExampleFlow{}
}

func (*ExampleFlow) GetSteps() []dex.StepDef {
	return []dex.StepDef{
		dex.DefineStartStep(ExampleStep{}),
		dex.DefineStep(Finish{}),
	}
}
```

Use `dex.None` for nil-only input/output and concrete structs for durable payloads.

A no-wait Step embeds the input-typed default and returns a durable decision:

[Pinned runnable source](https://github.com/superdurable/dex/blob/sdk-go/v0.12.1/examples/go/primitives/flow/workflow.go)
<!-- dex-source: examples/go/primitives/flow/workflow.go -->
```go
type Finish struct {
	dex.StepDefaultsNoWaitFor[int]
}

func (Finish) Execute(ctx dex.Context, input int) (*dex.StepDecision, error) {
	if err := Status.Set(ctx, "done"); err != nil {
		return nil, err
	}
	return dex.GracefulComplete(input + 1), nil
}
```

## Registry, Worker, and Client

Construct every Flow once, then pass the same definitions into the Registry used by Worker and Client. See the [registry](https://github.com/superdurable/dex/blob/sdk-go/v0.12.1/examples/go/registry/registry.go) and [bootstrap](https://github.com/superdurable/dex/blob/sdk-go/v0.12.1/examples/go/cmd/server/dex/dex.go). Controllers start with `client.StartFlow(ctx, flow, flowID, input, options)` and retain the run ID for diagnostics.

## Route by task

- Syntax/state semantics: [primitives](primitives.md)
- Application shape: [patterns](patterns.md)
- Real-server verification: [testing](testing.md)
- Client boundary design and retry ownership, before implementation: [error handling](error-handling.md)
- Persistence/maps/Streams: [data handling](data-handling.md)
- Histories/progress: [observability](observability.md)
- Open-Flow compatibility: [versioning](versioning.md)
- Go traps: [gotchas](gotchas.md)
- Locks/loading/heartbeat/cancellation: [advanced features](advanced-features.md)

## Completion checklist

Confirm every Step type and persistent definition is registered, errors are returned, Client calls have deadlines, tests use unique IDs and a real Dex Server, and application code does not depend on Dex Server internals.
