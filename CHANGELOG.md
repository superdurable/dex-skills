# Changelog

All notable changes to Dex Developer are documented here.

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
