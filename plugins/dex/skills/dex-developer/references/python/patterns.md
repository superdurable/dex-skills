# Python design patterns

Preserve each invariant, not merely the shape. Pinned files are runnable implementations.

## Parallel Steps

- **Static:** return `go_to_many` for a fixed set of Step movements. Branches are independent. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel/static_parallel_steps_flow.py).
- **Dynamic:** construct movements from runtime input; each branch receives retry-safe data. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel/dynamic_parallel_steps_flow.py).
- **Await all:** workers publish completion once and dead-end; coordinator waits for N Channel messages. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel/await_parallel_steps_flow.py).
- **First win:** winner cancels sibling executions; losers must tolerate cooperative cancellation and avoid uncompensated commits. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel/first_win_parallel_steps_flow.py).

[Pinned runnable source](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel/static_parallel_steps_flow.py)
<!-- dex-source: examples/python/dex_examples/patterns/parallel/static_parallel_steps_flow.py -->
```python
    def execute(self, context: Context, input: str) -> StepDecision:
        return go_to_many(
            StepMovement.of(WorkAStep, input),
            StepMovement.of(WorkBStep, input),
        )
```

## Parallel SubFlows

- **Basic:** make one `SubFlow` condition per request and wait for all; use when one parent can hold the batch. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/basic_parent_flow.py).
- **Long-lived parent:** RPC bounds/publishes queue; a loop drains children; stop plus empty is the completion invariant. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/advanced_long_live_parent_flow.py).
- **Short-lived parent:** bounded batch, atomic channel-empty close, explicit reuse for replacement run. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/advanced_short_live_parent_flow.py).
- **Wait for half:** race child with all-done, count once, wait for `(total+1)//2`; quorum is not universal success. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/wait_for_half_parent_flow.py).
- **Partitioning:** hash a stable affinity key into a fixed parent set. Version changes to partition topology. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/submit_request_flow.py).
- **Back pressure:** durable submit Flow turns rejection into Step retry/backoff; bound parent queue before acceptance. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/parallel-subflows/submit_request_flow.py).

## Polling and durable timers

- **Timer polling:** Timer in `wait_for`, then loop; no durable scheduling with `asyncio.sleep`. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/polling/simple_polling_flow.py).
- **Backoff:** not-ready is Execute failure governed by Step retry; bound attempts/time. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/polling/backoff_polling_flow.py).
- **Iteration:** next page token is durable Step input. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/polling/iteration_flow.py).
- **Cron:** race Timer with trigger/skip, scheduling current run and next wait durably. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/cron/cron_schedule_flow.py).
- **Reminder:** race Timer with opt-out and send once per iteration. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/reminders/reminder_flow.py).
- **Inactivity:** activity restarts wait; Timer moves to processing; coalesce bursts. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/inactiveness-tracker-timer/inactiveness_tracker_flow.py).

## Failure handling

- **Execute recovery:** proceed to idempotent compensation with enough durable input for the original commit. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/recovery/failure_recovery_flow.py).
- **WaitFor recovery:** proceed only when recovery can distinguish the failed wait and rebuild state. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/primitives/proceed_on_wait_failure/proceed_on_wait_failure_flow.py).
- **Manual recovery:** after exhaustion, wait on durable operator decision Channels exposed through action-verb RPCs. The pinned example exposes retry only; add a skip RPC and durable command-ID deduplication when the application needs those semantics. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/intervention/manual_recovery_flow.py).
- **Graceful timeout:** Handler policy plus explicit `handle_timeout` terminal decision; request needed map/channel loads. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/timeout/flow_graceful_timeout.py).

## Draining, interruption, responsive update, entity store

- **Internal drain:** coordinate parallel main/side Steps and finalize after accepted messages drain. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/drain-channels/internal/drain_internal_channels_flow.py).
- **External drain:** accept via RPC and atomically close only with Channels empty. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/drain-channels/external_publishing/draining_channel_flow.py).
- **Interruptible:** RPC records interrupt; short work slices check it between operations. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/interruptible/interruptible_execution_flow.py).
- **Responsive Step:** await one named Step completion, not whole Flow. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/wait-for-step-completion/controller.py).
- **Responsive Attribute:** wait for a revision match, keep the returned watermark, then reload durable state. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/products/job-post/controller.py).
- **Responsive Stream:** long-poll and resume from token; tolerate duplicates at retries. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/primitives/stream/controller.py).
- **Entity store:** AttributeMap instances plus Attribute Store; lock exactly the entity mutated by RPC. [Runnable](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/entity-store/user_profile_flow.py).

Python also has a runnable resource-control pattern, but it is not part of the current cross-language official catalog: [source](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/patterns/resource-control/controller_flow.py).

### Revision Attribute match

Initialize the integer revision Attribute to zero. Every state-changing Step or RPC must declare the same Attribute lock and increment the revision inside the locked invocation. The [Job Posting Flow](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/products/job-post/job_post_flow.py) demonstrates that mutation boundary.

Both `Client` and `AsyncClient` expose `wait_for_attribute_match`. Use `AttributeMatch.equal_to`, `not_equal_to`, `greater_than`, `greater_than_or_equal`, `less_than`, or `less_than_or_equal`. The singleton form accepts Flow ID, Attribute, match, and timeout. The AttributeMap form inserts the instance before the match. Both return the decoded matched value. Call the application's read RPC afterward. The revision is a coalescing watermark, not an event stream.

[Runnable revision wait](https://github.com/superdurable/dex/blob/a1f5f538f021666a8d9fee630af8580a20c313c0/examples/python/dex_examples/products/job-post/controller.py)
<!-- dex-source: examples/python/dex_examples/products/job-post/controller.py -->
```python
        revision = await app_state.client.wait_for_attribute_match(
            flow_id,
            app_state.job_post.update_version,
            AttributeMatch.greater_than(required_int_query("lastRevision")),
            timedelta(seconds=30),
        )
        job_info = await app_state.client.invoke_rpc(app_state.job_post.get, flow_id)
        return jsonify({"revision": revision, "jobInfo": asdict(job_info)})
```
