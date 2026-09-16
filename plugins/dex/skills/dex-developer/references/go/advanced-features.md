# Advanced Go features

Use these only after Flow boundaries and recovery are explicit.

## Selective loading, locks, and transactions

Ordinary Attributes and Channel size metadata load automatically; large AttributeMaps and pending Channel payloads are opt-in per handler. Load exact instances for entity work. A not-loaded error is modeling feedback, not absence.

Declare Attribute or map-instance locks when RPC/Step mutations conflict. Lock the smallest stable key. Keep remote I/O outside transaction/lock windows. Treat `RPCLockConflictError` as contention.

## Buffered Stream and heartbeat

`dex.NewBufferedTextStream` batches by interval/bytes. Flush at semantic boundaries and return errors. Stream writes are liveness frames but preserve the explicit heartbeat checkpoint.

[Pinned SDK contract](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/sdk-go/dex/contracts_test.go)
<!-- dex-source: sdk-go/dex/contracts_test.go -->
```go
	progress, err := dex.NewBufferedTextStream(
		context,
		progressStream,
		dex.BufferedTextStreamFlushInterval(500*time.Millisecond),
		dex.BufferedTextStreamMaxBytes(8<<10),
	)
```

Set heartbeat timeout for long Execute work. On retry, test whether a prior value exists before decoding; resume from an externally committed checkpoint. Heartbeat is progress, not authoritative business state.

## Cancellation, durability, timeout, BlobCache

A decision/RPC result can cancel selected Step types or siblings. Cancellation is cooperative; external calls need context cancellation and idempotency.

Sync durability waits for persistence acknowledgement. Async improves latency but can replay a recently acknowledged attempt after failure; restrict it to idempotent work and test replay. See [durability runnable](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/go/primitives/durability/workflow.go).

A timeout handler has its own timeout, retry, durability, locks, and state loads. It follows normal commit rules.

Open one BlobCache at bootstrap and share it with Client/Worker. Align path/capacity across replacements needing large values. It provides payload locality, not arbitrary durable files.
