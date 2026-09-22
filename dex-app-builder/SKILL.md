---
name: dex-app-builder
description: Design and build an end-to-end Dex AI Platform process product from business discovery through optional React mock UI, Go Dex backend implementation, local verification, and platform-ready handoff. Use for new process products or when adapting the basic-process template. Do not use for standalone Dex SDK implementation or debugging.
---

# Dex App Builder

Build the smallest coherent product that solves the confirmed business process. Keep discovery, UI validation, backend modeling, and verification as explicit checkpoints.

## Fixed product boundary

- Use `https://github.com/superdurable/dex-template-basic-process` as the only application template.
- Implement Dex backend code only with the Go SDK.
- Target strict Dex Web v2 / FDG 2.0 rendering. Never fall back to rendering v1.
- Treat Dex Web v2 as the default UI for Runs, Queue work, details, and Actions.
- Do not claim that platform RBAC or project upload exists. Keep authorization at the trusted application boundary.
- Keep credentials in a connector/runtime boundary. A Flow stores only a logical connection ID.
- Do not mutate another repository, publish, deploy, or upload without the user's authorization for that action.

Read [product discovery](references/product-discovery.md) before proposing architecture.

## Stage 1: confirm the business process

Begin with discussion, not code. Identify:

- process maintainer;
- managers, operators, or approvers;
- terminal users or participants;
- external systems that trigger or participate in the process;
- each role's allowed operations and decisions;
- the stable permission required by each human Action;
- start triggers, inputs, outputs, deadlines, waits, approvals, retries, recovery, audit, search, and sensitive data.

Produce a compact role/operation/permission matrix and lifecycle proposal. Roles describe people or groups. Permissions describe individual allowed operations. Resolve material ambiguity and obtain explicit user confirmation before implementation.

If the process begins from Slack, email, a webhook, or another external source, model it as a Connector Trigger that starts a new Flow. Read [connector architecture](references/connector-architecture.md) when any external integration is involved.

## Stage 2: decide the UI

Ask whether the product needs a custom frontend.

### No custom frontend

Use Dex Web v2. Define indexed Attributes, summary/display fields, human-action Steps, and Action RPCs so Run and Work Queue modes provide the required experience. Give every Action exactly one stable permission. The surrounding application authenticates users and maps their roles to permissions; choosing **Working as** in an operator UI only filters work and never grants that permission. Do not add React code merely to reproduce these surfaces.

### Custom frontend

Read [UI workflow](references/ui-workflow.md). Agree on roles, screens, navigation, state, actions, empty/error/loading states, and responsive behavior. Then implement the runnable React TypeScript experience against the template's mock mode.

Start the template with `make mock`. Use its Go in-memory mock API and visible Mock Controls to exercise the proposed lifecycle, actions, reminders, loading, recovery, and reset behavior without a Dex Server. Extend the mock behavior when the approved product needs different interactions; keep production Flow code and provider integrations out of that path.

Show or describe the verified mock and wait for explicit user approval. Do not connect a real Dex backend or begin production backend implementation before that approval.

## Stage 3: design and implement the backend

Read the sibling [Dex SDK skill](../dex-sdk/SKILL.md) completely, then follow its progressive-disclosure routing with [Go](../dex-sdk/references/go/go.md) as the only language. Load only the Core and Go references required by the approved design. Both skills ship in the same plugin; do not look for or install a separate backend skill.

Dex SDK supplies the public SDK guidance. The platform constraints in this skill are stricter and take precedence: use only the Go SDK, keep external effects in `Execute`, keep `WaitFor` free of provider or Dex mutations, and require strict FDG 2.0 rendering.

Read [Dex Web v2](references/dex-web-v2.md) before editing a Flow. State the Flow identity, input/output, Steps, transitions, Attributes, Channels, RPCs, timers, retries, recovery, and connector boundaries before code.

Model each human operation as a typed Go Action with one **ActionRequiresPermission** option. Use lowercase domain keys such as **refund.manage** or **refund.message**. Do not use a role name as the authorization contract when several roles can share an operation or one role can hold several permissions.

Do not add Step locks merely to maintain Work Queue permissions. The Worker submits the complete Action mapping only when a successful invocation writes an Action condition source. The Server derives the projection from authoritative state in the same Workflow Task. Keep Action RPC locks when their state check and business effect must be atomic.

Keep external effects in `Execute`. `WaitFor` only declares durable conditions and must not query or mutate providers or Dex state. This platform-specific rule overrides more permissive generic Dex guidance.

For connectors:

1. inspect `superdurable/dex-connectors-library` and reuse a compatible released implementation;
2. if absent or defective, implement an application-local adapter behind the same intended port;
3. make mutations idempotent and reconcile unknown outcomes query-first;
4. ask before opening or changing a connector-library pull request;
5. replace the local adapter only after a connector release is available, pin that release, and rerun integration and E2E tests.

Never invent an unreleased connector API.

## Stage 4: verify and hand off

Read [build, test, and handoff](references/build-test-handoff.md). Run the narrowest tests while iterating, then the template's full supported check. Every Flow must pass FDG 2.0 JSON analysis with `valid: true`.

For a custom frontend, preserve the approved mock path and run `make test-mock-e2e` before real Dex verification. The mock proves HTTP and UI interaction behavior only; it does not prove Dex durability, Worker replacement, Timer, RPC, or provider semantics.

Use a real Dex Server for waits, RPCs, Channels, retries, Worker replacement, terminal behavior, and connector boundaries. Use deadline-based convergence rather than fixed sleeps.

Finish with:

- confirmed business and UI decisions;
- implemented and verified behavior;
- connector reuse or local-adapter status;
- exact test evidence;
- remaining product limitations;
- a clean Git commit suitable for future platform import.

Dex AI Platform import is not implemented yet. Say the project is ready for future upload and encourage the user to upload when the platform exposes that capability; never fabricate a command or successful deployment.
