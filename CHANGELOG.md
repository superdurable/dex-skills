# Changelog

All notable changes to Dex Skills are documented here.

## 0.14.0 - 2026-09-24

- Require Dex Flow ID, start Request ID, and ID reuse policy to own root-start deduplication; prohibit dedicated database admission tables or other shadow deduplication mechanisms.
- Upgrade Dex App Builder to Server v0.11.4, Dex Web v2 v0.2.0, Go SDK v0.11.3, and basic-process release v0.1.0 with template contract v1.3.0.
- Require an explicit No custom UI or Custom UI decision during process discovery.
- Keep only a Hello World/OpenAPI architecture shell when Dex Web provides the complete management experience.
- Reserve generic HTTP for controlled internal systems and require released dedicated connectors for external providers.
- Add the authorized connector fork, upstream pull request, local verification, and release-blocker workflow.
- Refresh all pinned Dex SDK source links and language baseline versions.

## 0.13.0 - 2026-09-21

- Teach Dex App Builder to separate business roles from the permissions required by human Actions.
- Require one stable permission per Action and keep identity-to-permission authorization at the trusted application boundary.
- Document typed Go Action registration, UI slots, Work Queue discovery, and multi-permission search for Dex AI Platform applications.
- Explain Server-managed Action permission projection and remove projection-only Attribute locking from application guidance.
- Pin SDK source guidance to `sdk-go/v0.10.2` and Dex Web v2 guidance to merged pull request 517.

## 0.12.1 - 2026-09-21

- Guide Attribute designs to reuse namespace-level typed Search Attribute slots and scope raw generic-key queries with FlowType.
- Document stable domain-key exceptions, persistent local schema changes, and the prohibition on indexing PII.

## 0.12.0 - 2026-09-21

- Add the basic-process template's Go mock server and Mock Controls as the required custom-frontend interaction checkpoint before connecting a real Dex backend.
- Pin the supported template to version `1.2.0` and validate its `make mock` and `make test-mock-e2e` commands.
- Shorten the Codex plugin display name and GitHub release title to `Dex` while retaining plugin ID `superdurable-dex` and publisher `Super Durable`.
- Upgrade the Codex, Claude Code, and Cursor package metadata to `0.12.0`.

## 0.11.0 - 2026-09-21

- Rename the technical skill from `dex-developer` to `dex-sdk`.
- Add `dex-app-builder` for business discovery, optional UI prototyping, Go backend implementation, strict Dex Web v2 rendering, local verification, and future platform handoff.
- Publish both skills from the root of the `dex-skills` monorepo in one `superdurable-dex` plugin for Codex, Claude Code, and Cursor.
- Remove the nested plugin wrapper, backend companion skill, vendored SDK references, and cross-repository synchronization workflow.

## 0.10.2 - 2026-09-18

- Document the Indexed Attribute capacity left by Dex system indexes in local **dexcli dev** SQLite.
- Distinguish local SQLite slot exhaustion from production visibility-backend limits.

## 0.10.1 - 2026-09-17

- Distinguish query-only RPCs from Signal and Update paths after Flow termination.
- Clarify that successful read-only RPCs do not prove the Flow is active.
- Require terminal-path tests for query reads, returned effects, and transactional execution.

## 0.10.0 - 2026-09-17

- Document compact lowercase Base36 day offsets in Blob references.
- Explain readable, percent-escaped Flow IDs in physical Blob paths.
- Pin runnable sources to Dex release `sdk-go/v0.10.0`.

## 0.9.1 - 2026-09-17

- Make Flow-level durability defaults and method-level StepOptions a first-class Flow design decision.
- Document the ASYNC local phase, regular fallback, shared retry budget, and strict child-deadline requirement.
- Add the five-second ShortRunning/LongRunning heuristic and one-minute heartbeat guidance across all five SDKs.

## 0.8.2 - 2026-09-17

- Document explicit Go RPC registration and definition-time options.

## 0.8.1 - 2026-09-17

- Add race-safe handling for not-active Flow interactions and terminal child cleanup.
- Move shared Client failure policy into a pre-implementation core error-handling guide and route all Client-boundary work through it.
- Document stable start Request IDs and duplicate-start semantics for every SDK.
- Clarify Java's public remote-only `DexServiceException` boundary while preferring concrete domain exceptions.
- Document each SDK's distinct remote-error shape and best-effort Stream boundary.
- Clarify best-effort Stream failure handling and immutable admission projections for fast-closing Flows.
- Pin runnable sources to Dex commit `d5529248`.

## 0.8.0 - 2026-09-16

- Document Server and SDK protocol-interval negotiation during Worker startup.
- Explain first-time Server-first upgrades, compatible rolling upgrades, and breaking maintenance windows.
- Distinguish transport protocol compatibility from open-Flow graph and payload compatibility.
- Pin runnable sources to Dex commit `e93b803a`.

## 0.7.7 - 2026-09-15

- Document that successful ASYNC local Step input snapshots are opt-in and disabled by default.
- Clarify that snapshot storage affects semantic-history input availability, not execution or recovery.
- Pin runnable sources to Dex commit `4c18c7d0`.

## 0.7.6 - 2026-09-15

- Remove protocol-level minimum and maximum Blob object ID lengths.
- Document that readers accept any nonempty lowercase Base36 object ID.
- Pin runnable sources to Dex commit `068926a0`.

## 0.7.5 - 2026-09-15

- Document the Value null arm as the ordinary null representation across all five SDKs.
- Preserve null's boundary-specific meanings: Attribute deletion and omitted Flow completion output.
- Pin runnable sources to Dex commit `6ac5c0af`.

## 0.7.4 - 2026-09-15

- Document the final compact Blob reference shape, including six-digit UTC dates and lowercase Base36 object IDs.
- Explain that Object Blobs store the complete EncodedObject and references have no encoding suffix.
- Restore the explicit `json` and `raw` wire encodings without a compatibility format or versioned path.
- Pin runnable sources to Dex commit `52d43dc7`.

## 0.7.3 - 2026-09-15

- Document the 100-byte default Blob offload threshold and compact lowercase object identifiers.
- Treat internal Blob references as opaque, Flow-owned values with Flow-scoped SDK cache keys.
- Explain automatic Blob ownership transfer across Flow boundaries and the `j`/`r` standard wire encodings.
- Pin runnable sources to Dex commit `d806a958`.

## 0.7.2 - 2026-09-15

- Document deterministic **AnyOf** selection across ready Timer, Channel, and SubFlow conditions.
- Preserve declaration order within each condition kind while warning that mixed kinds have canonical order.
- Recommend returning only the active high-priority condition when a Flow requires strict priority.
- Pin runnable sources to Dex commit `61fa53c1`.

## 0.7.1 - 2026-09-14

- Document server-derived namespaced Request IDs for Step and Attribute waits.
- Document automatic `-N` generations after a durable wait handler times out.
- Recommend zero maximum wait time for ordinary waits and explain the in-flight Update tradeoff.
- Clarify actual matched Attribute values and pin runnable sources to Dex commit `905f39b6`.

## 0.7.0 - 2026-09-14

- Document durable Step and Attribute waits with required caller-owned Request IDs.
- Explain automatic transport reattachment, total handler budgets, infinite-wait lifecycle, and typed handler-timeout errors.
- Show that non-equal Attribute waits return the actual matched value for all five SDKs.
- Pin runnable sources to Dex commit `7ca1878dc`.

## 0.6.1 - 2026-09-13

- Document externally managed attribute indexes for Temporal Cloud API-key deployments.
- Require the three Dex system indexes and every indexed application Attribute to be provisioned before startup.
- Pin runnable sources to Dex commit `1f85cb52`.

## 0.6.0 - 2026-09-12

- Document the Dex Server image's default single-process Web, API, and Interpreter topology.
- Explain independent component deployment with `start --services` and Web-only remote FlowService configuration.
- Clarify Web liveness, upstream recovery, plaintext gRPC, ports, and split Interpreter-to-API wiring.
- Route deployment questions explicitly and distinguish reusable public test bootstrap from repository-only fixtures.
- Cover shared Redis and Blob Store requirements for replicated Server components.
- Tighten manual-command idempotency and Rust revision/recovery composition after isolated language evaluations.
- Pin runnable sources to Dex commit `a1f5f538`.

## 0.5.2 - 2026-09-11

- Prefer direct Flow-first orchestration for multi-step API mutations over database outbox dispatchers and generic event-driven coordinators.
- Retain domain data and read projections in the database while Dex owns durable execution, retries, waits, recovery, and cleanup.

## 0.5.1 - 2026-09-11

- Clarify that `Execute` and `WaitFor` are Flow-modeling phases rather than SDK capability boundaries.
- Allow safely retried provider queries or mutations in either phase when they establish or reconcile a transition.
- Explain when a provider action merits its own Step checkpoint, retry policy, recovery route, or audit boundary.

## 0.5.0 - 2026-09-11

- Make typed Flow RPCs the application boundary for Attribute, AttributeMap, Channel, and ChannelMap reads and writes.
- Retain Attribute match as the blocking observation API while removing guidance for deleted Client state APIs.
- Require action-verb RPC names and complete, precise names across application-facing definitions.
- Warn that Step and RPC pending-message snapshots can race with concurrent Channel mutations.
- Pin runnable examples to Dex commit `24f3a42a` and SDK releases 0.6.0, with Go at 0.6.1.

## 0.4.1 - 2026-09-10

- Prefer dedicated read-only RPCs for responses that combine multiple Attributes or AttributeMap instances.
- Preserve narrow read models instead of combining unrelated views to reduce reads.

## 0.4.0 - 2026-09-10

- Add reverse, non-blocking retained Stream pagination guidance for Python, Go, Java, TypeScript, and Rust.
- Distinguish best-effort newest-first listing from forward, resumable Stream consumption.
- Pin runnable listing examples and the released Dex SDK 0.5.0 dependencies to Dex commit `ffe799a3`.

## 0.3.1 - 2026-09-09

- Add the Super Durable brand mark to Codex and Cursor plugin surfaces.

## 0.3.0 - 2026-09-09

- Replace equality-only Attribute waits with typed Attribute matches across Python, Go, Java, TypeScript, and Rust.
- Document locked revision Attributes as coalescing watermarks for responsive application refreshes.
- Pin runnable matcher and read-RPC examples to Dex commit `4881ef2c`.

## 0.2.0 - 2026-09-09

- Add progressive-disclosure core and language handbooks for Python, Go, Java, TypeScript, and Rust.
- Cover the complete official Dex design-pattern catalog with language-native runnable sources.
- Pin exact API excerpts to a Dex source baseline and validate snippet fidelity in CI.
- Add detailed testing, errors, data, observability, versioning, gotchas, and advanced-feature guidance.
- Add isolated five-language behavior evaluations to the release verification process.

## 0.1.0 - 2026-09-09

- Extract the Dex Developer skill from Dex commit `05be5c42`.
- Package the skill as the portable `dex` Agent Plugin.
- Add Codex, Claude Code, and Cursor marketplace metadata.
- Document installation, invocation, caching, and update behavior.
