# TypeScript versioning

Open Flows may call a newly deployed Worker. Treat stable names and wire shapes as persisted interfaces: `getFlowType()`, `getStepType()`, Attribute/Channel/Stream names, RPC names, codec behavior, DTO fields, and Step graph decisions.

## Business continuity

Apply the shared [RunID boundary](../core/versioning.md#business-identity-and-continue-as-new).
Ordinary API/RPC DTOs and effect keys use stable business IDs/FlowID and domain
revisions. Continue-As-New preserves that lifecycle; it does not reset message
sequences, pending work, cursors or UI state. Keep SDK run selectors/return values
truthful but internal; exact RunID selection is for diagnosis/history or explicit
execution recovery. Test continuity without adding a current-run lookup.

## Server protocol compatibility

TypeScript builds embed the diagnostic package version. Worker startup calls `GetServerInfo`, negotiates the highest common protocol, synchronizes Attribute indexes, and then binds WorkerService. A missing RPC, invalid interval, or disjoint interval fails before binding. Upgrade a legacy Server first, and stop running Workers before a breaking Server release because they do not renegotiate.

## Before a rollout

1. Read the resolved `@superdurable/dex` version and lockfile.
2. Verify precise APIs against that release.
3. Inventory open Flows by type and Worker target/version.
4. Test an old-open Flow against the new Worker.
5. Decide how old and new behavior coexist and when old code can be removed.

Use additive fields with tolerant decoders where semantics allow. A compile-time optional property is not automatically wire-compatible. Renaming a Step class is harmless only if `getStepType()` remains stable and its registration/behavior remains compatible.

## Safe strategies

- Keep old Step and RPC implementations registered until open executions drain.
- Introduce a new Flow type or Worker target for incompatible graphs.
- Persist a business version Attribute at start and branch on that durable value.
- Route only new starts to the new version.
- Remove old code only after no running, waiting, retrying, or recoverable execution needs it.

Continue-as-new preserves the logical Flow ID and deadline semantics defined by the installed SDK. Retry creates a new run and may receive a new timeout budget. Neither transforms application state for you.

See the canonical [Application Operations versioning section](https://docs.superdurable.io/production/application-operations#versioning-flow-code).
