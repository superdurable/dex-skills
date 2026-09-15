# TypeScript data handling

## Codecs are runtime contracts

TypeScript types disappear at runtime. Use scalar codecs for scalar wire values and a deliberate `jsonCodec<T>` for objects. Add decode validation for untrusted or evolving data. Omitted codecs use JSON but do not validate object structure.

Stable Flow, Step, Attribute, Channel, Stream, RPC, and codec type names are part of open-Flow compatibility. Avoid renaming them as a cosmetic refactor.

## State shapes

Use Attributes for authoritative current state, AttributeMaps for independently loaded records, Channels for durable FIFO commands, ChannelMaps for per-key queues, and Streams for best-effort progress. Register each definition in one Flow schema.

[Pinned typed state source](https://github.com/superdurable/dex/blob/d806a958e6dd7a221ea5af817384e7fd13d347da/examples/typescript/src/primitives/attribute/attribute-flow.ts)
<!-- dex-source: examples/typescript/src/primitives/attribute/attribute-flow.ts -->
```typescript
const status = new Attribute("primitive-attribute-status", stringCodec, {
  type: IndexType.KEYWORD,
  indexKey: "OrderStatus",
});
const email = new Attribute("primitive-attribute-email", stringCodec).syncToAttributeStore();
const progress = new AttributeMap("primitive-attribute-progress", stringCodec, {
  type: IndexType.KEYWORD,
  indexKey: "OrderProgress",
});
```

Map instance keys must be stable, non-empty, and slash-free. Load only the instances/pending messages a handler reads. The effective map view includes mutations staged in the current handler, but RPC pending-message snapshots do not refresh after later staged writes.

## Commit boundary

Attribute changes and Channel publishes/deletes are staged and commit with the successful handler result. Ordinary module state, filesystem writes, and remote API calls are not durable mutations. Derive external idempotency keys from Flow ID plus a persisted business sequence.

## BlobCache and large data

Share one process BlobCache between Client and Worker. Large payload support does not make a growing JSON aggregate efficient. Partition mutable data into AttributeMap instances, put queued work on Channels, and emit transient progress on Streams.

The Server keeps payloads through 100 bytes inline by default. Treat internal blob references as opaque: hydration and cache lookup use the owning Flow ID with the reference, and Dex rewrites blob-backed values that cross into another Flow. Standard wire encodings are `j` for JSON and `r` for raw bytes.

Attribute Store is an asynchronous latest-state projection. Select Store names in `FlowConfig`; do not wait on projection as a correctness barrier.
