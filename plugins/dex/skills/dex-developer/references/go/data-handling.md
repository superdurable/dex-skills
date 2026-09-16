# Go data handling

Step input/output describes transitions; Attributes hold current state; AttributeMaps partition it; Channels hold queued intent; Streams hold incremental output; BlobCache carries large serialized values. Choose one authority for each fact.

## Schema and commit boundary

Definitions are stable package-level values registered in `PersistenceSchema`. Concrete generic types determine codecs. Treat exported fields/types as contracts for open Flows.

Writes through `dex.Context` are buffered in an invocation and commit with its successful result. Do not report success externally before return. On error, expect retry from the prior durable boundary.

## Maps and selective loading

Map instance names must be non-empty and contain no `/`. Request exact instances for entity handlers and whole maps only for scans. An unrequested instance raises a typed not-loaded error; that differs from an absent key.

## Streams and large values

Use Stream for replayable progress and Attribute for latest authoritative state. Persist resume tokens. Buffered text reduces write amplification but adds a flush boundary; flush final chunks.

Client and Worker share BlobCache for values beyond inline limits. Size it for the working set and use suitable local storage. Do not put large opaque payloads in indexed Attributes. See pinned [bootstrap](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/cmd/server/dex/dex.go) and [SDK guide](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-go/README.md).

The Server keeps payloads through 100 bytes inline by default. Treat internal blob references as opaque: hydration and cache lookup use the owning Flow ID with the reference, and Dex rewrites blob-backed values that cross into another Flow. String and Object references share a compact six-digit-date shape; their Value arms distinguish them. Object Blobs store the complete EncodedObject with `json`, `raw`, or a custom encoding, so references have no encoding suffix. The Server's `objectIdLength` defaults to 10, accepts any positive length, and treats zero as the default; readers accept any nonempty lowercase Base36 object ID.

ASYNC local Step input snapshots are disabled by default. Enable the Server's `blobStore.asyncStepInputSnapshotsEnabled` only when semantic history needs exact method inputs; it does not affect execution, retry, or recovery.

Go nil values use the Value null arm and decode through the requested Go type. In an Attribute write null deletes the Attribute, and as a Flow completion output it is discarded. Return an explicit result struct when terminal null and no output must differ.

## Evolution

Add payload fields compatibly, keep old variants readable, and never repurpose persisted fields. For breaking changes, add a new Flow/Step type and retain old definitions until open runs drain.
