# Product discovery

Do not start implementation until the product owner confirms the business model.

## Role and operation matrix

Capture at least:

| Actor | Goal | Can start | Can view | Can act | Can maintain |
| --- | --- | --- | --- | --- | --- |
| Process maintainer | Own process definition and policy | product-specific | all required operational state | recovery/configuration actions | definitions and integrations |
| Manager or operator | Review and resolve work | optional | assigned or scoped runs | approve, reject, edit, retry, escalate | no code by default |
| Terminal user | Request or participate | usually their request | their relevant status | supply requested information | no |
| External system | Trigger or exchange data | Trigger capability | query only when required | typed integration action/event | no |

Replace generic labels with domain names. Record which operations require authentication, authorization, audit, or a reason.

## Lifecycle questions

Confirm:

- business identity and unique Flow ID source;
- start trigger and duplicate-start behavior;
- typed start input and completion output;
- happy path and terminal business outcomes;
- human decisions, required fields, deadlines, reminders, and escalation;
- retryable provider failures versus business rejection;
- unknown external mutation outcomes and query-first reconciliation;
- cancellation, recovery, cleanup, and operator intervention;
- searchable/indexed fields and detailed display fields;
- sensitive data that must not enter IDs, logs, Streams, or generated artifacts.

## Confirmation artifact

Before code, provide:

1. the role/operation matrix;
2. a numbered lifecycle with decisions and terminal outcomes;
3. proposed Flow, Step, state, message, timer, RPC, and connector boundaries;
4. unresolved tradeoffs.

Ask for explicit confirmation. A casual discussion response is not approval to implement.
