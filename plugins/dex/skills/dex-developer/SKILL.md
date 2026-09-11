---
name: dex-developer
description: Develop, debug, test, and operate applications built with Superdurable Dex in Python, Go, Java, TypeScript, or Rust. Use when a user mentions Dex Flows, Steps, Attributes, Channels, Streams, RPCs, SubFlows, Workers, Dex Web, or dexcli. Do not activate for unrelated uses of the word "dex" or for Dex framework/server implementation work.
---

# Dex Developer

Build reliable applications through Dex's public programming model. Keep the user's experience in Dex terms and APIs.

## Stay at the application boundary

- Model behavior with Flows, Steps, Waits, Attributes, Channels, Streams, RPCs, Timers, SubFlows, Workers, and the Client.
- Use Dex Web, dexcli, SDK errors, and application logs for inspection and recovery.
- Use typed Flow RPCs as the application boundary for reading and writing Attributes, AttributeMaps, Channels, and ChannelMaps. Do not use removed Client state APIs. Attribute match remains the blocking observation API.
- Do not expose Dex Server internals as application requirements. Discuss them only when the user explicitly asks to develop Dex itself.
- Diagnose read-only by default. Do not stop, time travel, publish, invoke, delete, edit, or otherwise mutate a Flow unless the user authorizes it.

## Establish source authority

Before writing code, identify the language, package manager, installed Dex SDK version, registry, Worker and Client bootstrap, and repository test commands.

Preserve the installed SDK version unless the user asks to upgrade. The project's source, lockfile, installed SDK, and version-matched examples are authoritative. This bundle's exact API excerpts are pinned to the commit in `DEX_BASELINE`; use them as guidance, not as evidence that a different installed version has the same signature.

If the project version differs from the baseline, name the matching installed-source path or immutable tag/commit used before writing exact API code. If that source is unavailable, stop at the version-independent Flow model, identify what is needed, and ask to inspect or fetch it. Never claim verification without an auditable version-matched source, label baseline syntax as compatible with an unverified version, or invent a Dex API.

## Load references progressively

Always read the entry page for the project's language first:

- [Python](references/python/python.md)
- [Go](references/go/go.md)
- [Java](references/java/java.md)
- [TypeScript](references/typescript/typescript.md)
- [Rust](references/rust/rust.md)

Then load only the references required by the task:

| Task | Core reference | Language reference |
| --- | --- | --- |
| First application or architecture | [Getting started](references/core/getting-started.md) | language entry |
| Flow boundary or state model | [Modeling](references/core/modeling.md) | selected language's **primitives.md** |
| Primitive selection or exact API | [Primitives](references/core/primitives.md) | selected language's **primitives.md** |
| Design-pattern choice | [Patterns](references/core/patterns.md) | selected language's **patterns.md** |
| Integration or failure-path tests | [Testing](references/core/testing.md) | selected language's **testing.md** |
| Failure diagnosis | [Troubleshooting](references/core/troubleshooting.md) | selected language's **error-handling.md** and **gotchas.md** |
| Production inspection or mutation | [Operations](references/core/operations.md) | selected language's **observability.md** |
| Large state, maps, or projections | [Data handling](references/core/data-handling.md) | selected language's **data-handling.md** |
| Open-Flow compatibility or upgrade | [Versioning](references/core/versioning.md) | selected language's **versioning.md** |
| Heartbeats, cancellation, selective loading, locks, BlobCache, or async durability | relevant core topic | selected language's **advanced-features.md** |
| Durable AI agent | [AI agents](references/core/ai-agents.md) | selected language's primitives, data, patterns, and advanced features |

The language directory is the routing unit. Do not load all five languages.

## Model before implementation

For non-trivial work, first state the Flow identity and lifecycle, typed start input and completion output, Steps and transitions, durable state, messages, synchronous RPCs, best-effort Streams, timers, retries, timeouts, recovery, and SubFlow boundaries.

Name every RPC handler and explicit RPC with a concrete action verb. Use complete domain names such as `get_queued_messages` or `move_queued_message_to_prioritized_messages`, not noun-only names, placeholders, or generic names such as `Get`, `Update`, `Manager`, `Data`, or `Handler`. Apply the same preference for complete, precise names to APIs, interfaces, classes, types, methods, functions, fields, variables, and constants. Brevity is not a goal; a name should communicate its operation and subject at the call site or registration boundary.

Keep external side effects in **Execute**. Use **WaitFor** to declare durable conditions and prepare wait-local state. Make every transition and terminal decision explicit. Treat each WaitFor, Execute, and RPC invocation as a separate commit boundary; external effects still require idempotency or compensation.

Prefer the nearest official pattern to an ad hoc coordination loop. Preserve its Flow shape while replacing the domain and integrations. When changing a Go or Python Flow, use `dexcli visualize SOURCE` after the shape is explicit; the visualizer does not currently support Java, TypeScript, or Rust.

## Complete the vertical slice

Application changes should include typed inputs, outputs, and failures; Flow and Step definitions; every persistence schema entry; constructor-injected dependencies; registry wiring; Worker and Client wiring when absent; an application boundary; and a real Dex Server integration test.

Keep stable Flow, Step, Attribute, Channel, Stream, and RPC names compatible with open executions unless the user has an explicit migration. Use unique Flow IDs and convergence polling rather than fixed sleeps.

Before handoff, verify build or type-check, the relevant integration scenario, registration of every durable primitive, retry and timeout recovery, duplicate requests, terminal behavior, heartbeat cadence, Stream best-effort semantics, and compatible Worker/Client registry and payload configuration.
