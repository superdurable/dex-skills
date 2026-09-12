# Changelog

All notable changes to Dex Developer are documented here.

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
