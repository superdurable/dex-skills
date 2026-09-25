# Product discovery

Do not start implementation until the product owner confirms the business model.

## Role, operation, and permission matrix

Capture at least:

| Actor | Goal | Can start | Can view | Actions and permissions | Can maintain |
| --- | --- | --- | --- | --- | --- |
| Process maintainer | Own process definition and policy | product-specific | all required operational state | recovery/configuration Actions with explicit permissions | definitions and integrations |
| Manager or operator | Review and resolve work | optional | assigned or scoped runs | approve, reject, edit, retry, or escalate with one permission per Action | no code by default |
| Terminal user | Request or participate | usually their request | their relevant status | supply requested information with an explicit permission when exposed as an Action | no |
| External system | Trigger or exchange data | Trigger capability | query only when required | typed integration Action or event | no |

Replace generic labels with domain names. Record which operations require authentication, authorization, audit, or a reason. Keep roles and permissions separate: a role can hold several permissions, and several roles can share one permission.

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

## UI-mode decision

Ask directly whether the product needs a custom process UI. Evaluate Dex Web
first: Run and Work Queue already provide Flow search, indexed columns, summary
and display fields, editable scalar fields, Action forms, and permission-based
work discovery.

Choose **No custom UI** when those surfaces satisfy operators and maintainers.
Keep only the template's non-business Hello World/OpenAPI architecture for
future evolution. Confirm whether the existing host supplies authentication,
role-to-permission mapping, project/tenant isolation, and a trusted reverse
proxy. Those controls may still be required, but they are not a second process
management backend.

Choose **Custom UI** only for confirmed requirements such as participant-facing
journeys, bespoke navigation, branding, domain visualization, or interactions
Dex Web cannot provide. Record which requirement forces the custom surface.

## Connector decision

List every external Trigger, Query, Mutation, and integration UI. Match
each to a released dedicated connector before implementation. Mark an endpoint
as internal only when the organization owns and controls it; only those
connections may use the generic HTTP connector. Record every missing connector
as a fork/PR work item and production release blocker.

## Confirmation artifact

Before code, provide:

1. the role/operation/permission matrix;
2. a numbered lifecycle with decisions and terminal outcomes;
3. the confirmed **No custom UI** or **Custom UI** mode and its reason;
4. proposed Flow, Step, state, message, timer, RPC, and connector boundaries;
5. connector reuse, fork/PR, and release status;
6. unresolved tradeoffs.

Ask for explicit confirmation. A casual discussion response is not approval to implement.
