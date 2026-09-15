# Python data handling

Use dataclasses or other explicit typed models for durable payloads. Avoid `Any`, arbitrary object graphs, lambdas, open file handles, and process-local state. Persisted field names/types are compatibility contracts.

Attributes hold current state; AttributeMaps partition it; Channels hold queued intent; Streams hold progress; Step inputs/outputs describe transitions. Context writes commit with successful invocation return. On exception, expect replay from the prior boundary.

Map instance names are non-empty and contain no `/`. Select exact instances for entity handlers. `AttributeMapNotLoadedError` means the snapshot omitted the entry, not that it does not exist.

Use Stream for incremental output and Attribute for authoritative latest state. Persist read tokens. Buffered text adds a flush boundary; async writer `write` is synchronous while `context.heartbeat` is awaited. A sync buffered writer produces outputs that must be yielded.

Share one BlobCache with Client and Worker for large payloads. Capacity/path are deployment concerns. BlobCache is payload locality, not general durable filesystem state. See pinned [async composition](https://github.com/superdurable/dex/blob/d806a958e6dd7a221ea5af817384e7fd13d347da/examples/python/dex_examples/app.py) and [SDK guide](https://github.com/superdurable/dex/blob/d806a958e6dd7a221ea5af817384e7fd13d347da/sdk-python/README.md).

The Server keeps payloads through 100 bytes inline by default. Treat internal blob references as opaque: hydration and cache lookup use the owning Flow ID with the reference, and Dex rewrites blob-backed values that cross into another Flow. Standard wire encodings are `j` for JSON and `r` for raw bytes.

For incompatible serialization changes, introduce a new Flow/Step type and keep old definitions until open runs drain.
