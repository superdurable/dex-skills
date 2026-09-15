# Java data handling

## Types and serialization

`Step<I>` exposes `Class<I> getInputType()`. Use concrete DTO classes, records supported by the configured mapper, scalar wrapper classes, or arrays. Do not use `List<Foo>.class`; wrap parameterized structures in a named input type. Keep wire field names and meanings compatible with open Flows.

Define each Attribute, AttributeMap, Channel, ChannelMap, and Stream once per Flow type. Register every definition in `PersistenceSchema`. Names are durable identifiers, not refactoring-only symbols.

## Attributes and Channels

Use Attributes for current authoritative state and Channels for ordered pending work. AttributeMap and ChannelMap isolate values by stable instance key. Avoid loading an entire map when one instance is enough. RPC and Step load options control what reaches the Worker; reads outside the selected scope fail rather than silently fetching.

Locks provide cooperation among handlers using the same lock. Mark an RPC transactional when Channel deletion must abort the whole RPC on a missing message. A staged publish or Attribute write commits only with the successful handler result.

## Large values and BlobCache

Share one disk `BlobCache` between Worker and Client and size it for active payload locality. Blob storage makes large values feasible; it does not make repeatedly rewriting a growing aggregate cheap. Prefer an AttributeMap for independently updated records, Channels for durable queues, and Streams for best-effort deltas.

The Server keeps payloads through 100 bytes inline by default. Treat internal blob references as opaque: hydration and cache lookup use the owning Flow ID with the reference, and Dex rewrites blob-backed values that cross into another Flow. Standard wire encodings are `j` for JSON and `r` for raw bytes.

[Pinned cache construction](https://github.com/superdurable/dex/blob/d806a958e6dd7a221ea5af817384e7fd13d347da/examples/java/src/main/java/io/superdurable/dex/config/DexConfig.java)
<!-- dex-source: examples/java/src/main/java/io/superdurable/dex/config/DexConfig.java -->
```java
        return BlobCache.open(new BlobCacheConfig(blobCacheDir, 1L << 30));
```

## Attribute Store

Call `syncToAttributeStore()` on definitions that need an external latest-state projection and select Store names in `FlowConfig`. Projection is asynchronous and does not replace Flow state. Deletion projects null. Never make correctness depend on projection timing.

## Schema review

- Is each definition name stable and unique within the Flow?
- Is every map instance key non-empty, slash-free, and derived from a business identity?
- Does each handler load only the collections it reads?
- Are large mutable aggregates split by locality?
- Are external effects idempotent with keys derived from durable Flow state?
