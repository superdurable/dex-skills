# Dex Web v2 and FDG 2.0

Baseline: Dex commit `9c1d2d0d986b21c47c7c9be9cc3abd5125a16801`, containing the Run and Work Queue experience through merged Dex pull request 517.

Web v2 is Go-only. Validate every Flow with the v2 analyzer and never fall back to v1.

## Run and Work Queue surfaces

Dex Web derives its experience from:

- indexed Attributes for list and search columns;
- `GetDexSummary` for additional read-only list fields;
- `GetDexDisplay` for run detail fields;
- Step groups and explanations for the run timeline;
- waits on Channels/ChannelMaps for actionable human work;
- eligible Action RPCs for operator operations.

**Working as** selects one declared Action permission and filters Work Queue candidates. It does not authenticate a user or grant permission. A trusted application maps authenticated roles to permissions. Its **POST /api/v2/search** request may send several **workQueuePermissions**; a run matches any requested permission, then Flow type and other filters apply with AND.

## Source layout

For each Flow, keep all of these in one Go file:

- Step and Flow definitions;
- Attributes and other persistence declarations;
- Action input structs;
- `GetDexSummary`, `GetDexDisplay`, and Action handlers;
- all `dex:*` directives;
- transitions and Dex decisions.

## Directives

Every Step declares exactly:

```go
// dex:group group-id:review group-label:"Review"
// dex:explanation text:"Wait for a manager to approve the request."
```

Every indexed Attribute has one exact directive and `dex.Indexed` declaration:

```go
// dex:indexed-attribute attribute-key:case-status index-key:case-status index-type:keyword value-type:string description:"Current case status"
var CaseStatus = dex.DefineAttribute[string](
    "case-status",
    dex.Indexed(dex.AttributeIndex{Type: dex.IndexKeyword}),
)
```

Use `// dex:field` on summary and display RPCs. Summary fields are not editable and cannot duplicate indexed Attributes. Returned map keys exactly equal declared field keys. A display field may use `ui-slot:title`, `ui-slot:subtitle`, `ui-slot:status`, `ui-slot:recommendation`, or `ui-slot:reason`. The first four are unique within a view; reason may repeat.

Register every Action through `RPCOptions.Action`. `DefineAction` takes the label, one Attribute condition, and exactly one stable permission:

```go
dex.DefineRPC(flow.ApproveRequest, &dex.RPCOptions{
    Action: dex.DefineAction(
        "Approve",
        dex.WhenAttributeMatches(
            caseStatus,
            dex.AttributeMatchEqual(statusAwaitingApproval),
        ),
        dex.ActionRequiresPermission("request.approve"),
    ),
    LockAttributes: []dex.AttributeLock{
        dex.LockAttribute(caseStatus),
        dex.LockAttribute(approvalRequestKey),
    },
})
```

The analyzer reads this typed registration. Do not add `dex:action` or `dex:when` directives; they are rejected. An Action RPC re-checks current state before its durable mutation or Channel effect. Lock only the business state and effect that must commit atomically.

An Action without input uses `dex.None`. Otherwise every exported JSON field in a named same-file input struct has one `dex:input`. User-sourced inputs omit `attribute-key`; attribute-sourced inputs require a matching scalar Attribute.

## Permission projection

The Go Worker includes the complete Action permission mapping only when a successful WaitFor, Execute, timeout Execute, or RPC invocation writes or deletes an Action condition source. Unrelated writes, failed invocations, and query-only RPCs omit it. Initial Flow and SubFlow state receives its projection directly from the Go SDK, including RPC-only Flows.

The Server overlays those business writes on authoritative Attribute state, evaluates every mapping, sorts and deduplicates the available permissions, and updates `DexWorkQueuePermissions` in the same Workflow Task. It skips an unchanged projection and removes an empty one. Application Steps do not need projection-only Attribute locks.

Dex Web follows the same rule for editable fields: only `SetAttributes` calls that modify an Action condition source include the complete mapping. An Action definition is a stable contract for an active Flow. Deploying changed or removed mappings does not migrate existing state until a later source write, an explicit empty mapping, or a new run applies that definition.

## Validation

Run:

```bash
dexcli visualize path/to/flow.go \
  --schema-version 2.0 \
  --json \
  --out /tmp/flow-fdg-v2.json
```

Require the JSON graph to report `valid: true`. Treat diagnostics for missing or repeated directives, mismatched keys/types, non-read-only views, invalid typed Action registration, invalid Action inputs, or unsupported editable fields as blocking defects.
