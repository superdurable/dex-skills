# Dex Web v2 and FDG 2.0

Baseline: Dex commit `78c810baf027bcc02dd556b6046f4bd8baafc402`, containing the Run/Queue work and the Go rendering polish from Dex pull requests 511 and 512.

Web v2 is Go-only. Validate every Flow with the v2 analyzer and never fall back to v1.

## Run and Queue surfaces

Dex Web derives its experience from:

- indexed Attributes for list/search columns and action eligibility;
- `GetDexSummary` for additional read-only list fields;
- `GetDexDisplay` for run detail fields;
- Step groups and explanations for the run timeline;
- waits on Channels/ChannelMaps for actionable human work;
- eligible Action RPCs for operator operations.

Role-based platform authorization is not part of the current contract.

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

Use `// dex:field` on summary and display RPCs. Summary fields are not editable and cannot duplicate indexed Attributes. Returned map keys exactly equal declared field keys.

Every Action RPC declares one action and one eligibility condition:

```go
// dex:action action-label:"Approve"
// dex:when attribute-key:case-status operator:in values:["awaiting-approval"]
```

An Action without input uses `dex.None`. Otherwise every exported JSON field in a named same-file input struct has one `dex:input`. User-sourced inputs omit `attribute-key`; attribute-sourced inputs require a matching scalar Attribute.

## Validation

Run:

```bash
dexcli visualize path/to/flow.go \
  --schema-version 2.0 \
  --json \
  --out /tmp/flow-fdg-v2.json
```

Require the JSON graph to report `valid: true`. Treat diagnostics for missing or repeated directives, mismatched keys/types, non-read-only views, invalid Action inputs, or unsupported editable fields as blocking defects.
