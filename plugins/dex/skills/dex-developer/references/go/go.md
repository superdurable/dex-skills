# Go handbook

Use this page first for a Go application. It describes the application boundary and points to focused pages; always check the version selected by `go.mod` and `go.sum`.

## Version and source authority

The [baseline module](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/go.mod) uses `github.com/superdurable/dex/sdk-go v0.6.1`. Before editing an existing project, run `go list -m github.com/superdurable/dex/sdk-go` and inspect that SDK version. If it differs from the baseline, installed source wins. Identify the inspected module-cache path, vendored path, or immutable tag/commit before presenting exact syntax. If no version-matched source is available, give only the version-independent Flow model and request that source; do not adapt baseline snippets speculatively. Pinned sources show known-good shapes, not a promise that every version has the same surface.

## Project shape and local run

Keep Flow and Step definitions in application packages, compose them in one registry package, and create one shared Registry and BlobCache for Client and Worker. Inject business services into Flow constructors. The official example layout is `products/`, `patterns/`, `primitives/`, `registry/`, `shared/`, and `cmd/server/`.

```bash
dexcli dev
cd examples/go
make bins
./dex-samples
```

Defaults use Dex at `localhost:8801`, a Worker listener at `127.0.0.1:8803`, and HTTP at `127.0.0.1:8080`. `DEX_WORKER_TARGET` is the address advertised to Dex and can differ from the bind address.

## Minimal Flow

Declare schema at package scope, embed defaults, register Step types, and return a decision from every Execute method.

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/primitives/flow/workflow.go)
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
		dex.DefineStep(FinishStep{}),
	}
}
```

Use `dex.None` for nil-only input/output and concrete structs for durable payloads.

A no-wait Step embeds the input-typed default and returns a durable decision:

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/primitives/flow/workflow.go)
<!-- dex-source: examples/go/primitives/flow/workflow.go -->
```go
type FinishStep struct {
	dex.StepDefaultsNoWaitFor[int]
}

func (FinishStep) Execute(ctx dex.Context, input int) (*dex.StepDecision, error) {
	if err := Status.Set(ctx, "done"); err != nil {
		return nil, err
	}
	return dex.GracefulComplete(input + 1), nil
}
```

## Registry, Worker, and Client

Construct every Flow once, then pass the same definitions into the Registry used by Worker and Client. See the [registry](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/registry/registry.go) and [bootstrap](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/cmd/server/dex/dex.go). Controllers start with `client.StartFlow(ctx, flow, flowID, input, options)` and retain the run ID for diagnostics.

## Route by task

- Syntax/state semantics: [primitives](primitives.md)
- Application shape: [patterns](patterns.md)
- Real-server verification: [testing](testing.md)
- Typed failures/retry ownership: [error handling](error-handling.md)
- Persistence/maps/Streams: [data handling](data-handling.md)
- Histories/progress: [observability](observability.md)
- Open-Flow compatibility: [versioning](versioning.md)
- Go traps: [gotchas](gotchas.md)
- Locks/loading/heartbeat/cancellation: [advanced features](advanced-features.md)

## Completion checklist

Confirm every Step type and persistent definition is registered, errors are returned, Client calls have deadlines, tests use unique IDs and a real Dex Server, and application code does not depend on Dex Server internals.
