# Rust design patterns

Choose a pattern only after naming the durable state, external events, retries, completion boundary, and cancellation policy. Every implementation below is pinned to the Dex baseline. Reuse the Flow shape and invariants; adapt business types without renaming stable definitions in an already-running Flow.

## Parallel Steps

### Static fan-out

Use a fixed fan-out when the branches and their types are known at registration time. Clone owned input only where two movements need it. Each branch decides independently; normal Flow completion accounts for all branches.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel/parallel_step_flows.rs)
<!-- dex-source: examples/rust/src/patterns/parallel/parallel_step_flows.rs -->
```rust
    fn execute(&self, _: &mut Context, input: String) -> HandlerResult<StepDecision> {
        Ok(StepDecision::go_to_many([
            StepMovement::to(&WorkA, input.clone()),
            StepMovement::to(&WorkB, input),
        ]))
    }
```

### Dynamic fan-out

Use one registered Step type with runtime-sized inputs. Keep each movement self-contained and idempotent. Avoid an unbounded count; admission control belongs before fan-out.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel/parallel_step_flows.rs)
<!-- dex-source: examples/rust/src/patterns/parallel/parallel_step_flows.rs -->
```rust
    fn execute(&self, _: &mut Context, count: usize) -> HandlerResult<StepDecision> {
        Ok(StepDecision::go_to_many(
            (0..count).map(|index| StepMovement::to(&DynamicWork, index)),
        ))
    }
```

### Await all

Use a dedicated Channel as a durable join counter. Workers publish exactly once after their result is durably safe, then dead-end. The waiter uses `for_n(count)`. Make the publication idempotent or identify messages when external effects can be replayed.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel/parallel_step_flows.rs)
<!-- dex-source: examples/rust/src/patterns/parallel/parallel_step_flows.rs -->
```rust
    fn wait_for(&self, _: &mut Context, count: usize) -> HandlerResult<Wait> {
        Ok(Wait::until(COMPLETE.for_n(count)))
    }
    fn execute(&self, _: &mut Context, count: usize) -> HandlerResult<StepDecision> {
        Ok(StepDecision::graceful_complete(count))
    }
```

### First win

Use first-win when one valid result is sufficient. The winner must cancel sibling executions; all competitors must tolerate cooperative cancellation and duplicated external attempts.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel/parallel_step_flows.rs)
<!-- dex-source: examples/rust/src/patterns/parallel/parallel_step_flows.rs -->
```rust
    fn execute(&self, _: &mut Context, input: usize) -> HandlerResult<StepDecision> {
        thread::sleep(Duration::from_millis(fastrand::u64(50..500)));
        Ok(StepDecision::graceful_complete(input).cancel_sibling_step(&FirstWinWork))
    }
```

## Parallel SubFlows

SubFlows isolate child lifecycle and scale beyond one parent Step graph. Child input/output must be serde-compatible. Decide whether the parent needs every child, a quorum, or continuous admission.

### Basic fan-out

Create one `SubFlow::run` Condition per request and wait for all. This is appropriate for a bounded batch. Child failure participates in the parent's wait result; model failure handling rather than ignoring it.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel_subflows/flow.rs)
<!-- dex-source: examples/rust/src/patterns/parallel_subflows/flow.rs -->
```rust
    fn wait_for(&self, _context: &mut Context, requests: Self::Input) -> HandlerResult<Wait> {
        let child = ExampleSubFlow::default();
        let mut conditions = Vec::with_capacity(requests.len());
        for request in requests {
            conditions.push(SubFlow::run(&child, request).map_err(HandlerError::from_error)?);
        }
        Ok(Wait::all_of(conditions))
    }
```

### Wait for half

Fan out one branch per child and one quorum waiter. Each child branch waits on either its SubFlow or an all-done Channel. Once `div_ceil(2)` completions arrive, publish enough all-done messages to release remaining branches, whose injected Client cancels still-running child Flow IDs. Empty input must complete without underflow.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel_subflows/flow.rs)
<!-- dex-source: examples/rust/src/patterns/parallel_subflows/flow.rs -->
```rust
    fn wait_for(&self, _context: &mut Context, total: Self::Input) -> HandlerResult<Wait> {
        Ok(Wait::until(SUB_FLOW_COMPLETED_CH.for_n(total.div_ceil(2))))
    }

    fn execute(&self, context: &mut Context, total: Self::Input) -> HandlerResult<StepDecision> {
        for _ in 0..total - total.div_ceil(2) {
            ALL_DONE_CH.publish(context, true)?;
        }
        Ok(StepDecision::graceful_complete(()))
    }
```

### Long-lived parent

Use a bounded number of looping handlers for continuous work. An RPC enqueues requests; each handler consumes one, waits for a child, then loops unless a durable stop Attribute is set. The parent stays open and accepts future requests. Stop must prevent another loop and define what happens to queued work.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel_subflows/flow.rs)
<!-- dex-source: examples/rust/src/patterns/parallel_subflows/flow.rs -->
```rust
    fn execute(&self, context: &mut Context, _request: String) -> HandlerResult<StepDecision> {
        if STOPPED.get(context)?.unwrap_or(false) {
            return Ok(StepDecision::graceful_complete(()));
        }
        Ok(StepDecision::go_to(&LongLiveHandleRequestStep, ()))
    }
```

### Short-lived parent

Use a locked active-child count when the parent should finish after the queue drains. Each handler increments before starting a child and decrements afterward. `force_complete_if_channels_empty` atomically chooses completion only when the active count is zero and the request Channel is empty; otherwise it re-enters the receiver.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel_subflows/flow.rs)
<!-- dex-source: examples/rust/src/patterns/parallel_subflows/flow.rs -->
```rust
        if current == 0 {
            return Ok(StepDecision::force_complete_if_channels_empty(
                (),
                StepMovement::to(&ShortLiveHandleRequestStep, ()),
                [REQUEST_CHANNEL.when_empty()],
            ));
        }
```

### Partitioning and back pressure

Partition a stable request key over an explicit parent-ID set so related work reaches the same parent. The parent RPC returns `false` when its durable queue is at capacity. The submitting Flow converts rejection into a retryable handler failure, preserving durable retry instead of dropping the request. Adding or removing parent IDs changes the partition mapping; plan that migration.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/parallel_subflows/flow.rs)
<!-- dex-source: examples/rust/src/patterns/parallel_subflows/flow.rs -->
```rust
        let parent_id = &input.parent_ids[partition(&input.request, input.parent_ids.len())];
        let client = self.client.as_ref().ok_or_else(|| {
            HandlerError::new("ParallelSubFlows", "Dex client is not initialized")
        })?;
        let accepted = enqueue_request(client, parent_id, input.request)?;
        if !accepted {
            return Err(HandlerError::new(
                "ParallelSubFlows",
                format!("parent {parent_id} rejected the request"),
            ));
        }
```

## Polling

### Timer polling

Use a durable Timer between polls when every attempt should be a distinct Step execution. Carry the remaining count or cursor in Step input, and loop with `go_to`.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/polling/flow.rs)
<!-- dex-source: examples/rust/src/patterns/polling/flow.rs -->
```rust
    fn wait_for(&self, _context: &mut Context, _input: Self::Input) -> HandlerResult<Wait> {
        Ok(Wait::until(Timer::by_duration(Duration::from_secs(5))))
    }
```

### Retry-backoff polling

Use Execute retry when “not ready” is naturally a retryable failure of one logical method. Configure initial interval, coefficient, maximum interval, and maximum attempts. Do not use it when every poll must emit a durable business event.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/polling/flow.rs)
<!-- dex-source: examples/rust/src/patterns/polling/flow.rs -->
```rust
    fn options(&self) -> StepOptions<Self::Input> {
        StepOptions::new().execute_retry(
            RetryPolicy::new()
                .initial_interval(Duration::from_secs(1))
                .backoff_coefficient(2.0)
                .maximum_interval(Duration::from_secs(30))
                .maximum_attempts(8),
        )
    }
```

### Iteration

Use Step input as the durable page token and schedule the same Step until the source returns no next token. Make processing for one page idempotent before advancing the token.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/polling/flow.rs)
<!-- dex-source: examples/rust/src/patterns/polling/flow.rs -->
```rust
        if next_page_token.is_empty() {
            Ok(StepDecision::graceful_complete(()))
        } else {
            Ok(StepDecision::go_to(
                &IterationStep,
                next_page_token.to_owned(),
            ))
        }
```

## Durable timers

### Cron-like schedule

Loop a Timer-backed scheduling Step, optionally raced with trigger and skip Channels. Run work on a sibling branch so the next schedule remains durable. Bound runs in the sample; for an indefinitely open Flow, define versioning and shutdown behavior.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/cron/flow.rs)
<!-- dex-source: examples/rust/src/patterns/cron/flow.rs -->
```rust
        Ok(Wait::any_of([
            Timer::by_duration(state.interval.duration()),
            TRIGGER.for_one(),
            SKIP.for_one(),
        ]))
```

### Reminder

Race each reminder Timer with an opt-out Channel. A timer win records/sends the reminder and loops; opt-out completes. External notification must be idempotent because Execute may retry.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/reminders/flow.rs)
<!-- dex-source: examples/rust/src/patterns/reminders/flow.rs -->
```rust
        if !context.has_any_timer_fired() {
            return Ok(StepDecision::graceful_complete("opted-out".to_string()));
        }
        context.record_event("reminder", "sent".to_string())?;
        Ok(StepDecision::go_to(&ReminderStep, ()))
```

### Inactivity tracking

Race a long Timer with an activity Channel. Activity restarts the tracker Step and therefore resets the durable timer; timer expiry moves to inactivity processing. Decide whether bursts should consume one or drain all activity messages.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/inactiveness_tracker/flow.rs)
<!-- dex-source: examples/rust/src/patterns/inactiveness_tracker/flow.rs -->
```rust
        if context.has_any_timer_fired() {
            return Ok(StepDecision::go_to(&ProcessInactivenessStep, ()));
        }
        Ok(StepDecision::go_to(&TrackerStep, ()))
```

## Failure handling

### Execute recovery

Attach `on_execute_failure_proceed_to` after a bounded retry policy. The recovery Step receives the failed Step input and compensates or records a durable alternative outcome.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/recovery/flow.rs)
<!-- dex-source: examples/rust/src/patterns/recovery/flow.rs -->
```rust
    fn options(&self) -> StepOptions<Self::Input> {
        StepOptions::new()
            .execute_retry(RetryPolicy::new().maximum_attempts(3))
            .on_execute_failure_proceed_to(&Compensate)
    }
```

### WaitFor recovery

Set `WaitForFailurePolicy::Proceed` with bounded WaitFor retry and branch in Execute on `context.wait_for_method_failed()`. The runnable implementation is [ProceedOnWaitFailureFlow](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/proceed_on_wait_failure/flow.rs). Keep it separate from Execute recovery because its commit boundary and error source differ.

### Manual recovery

After Execute retries exhaust, proceed to a manual Step that waits for retry or skip Channels. A retry schedules the work with a changed input; skip force-fails the Flow. Authenticate and audit the controller endpoints that publish these decisions.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/intervention/flow.rs)
<!-- dex-source: examples/rust/src/patterns/intervention/flow.rs -->
```rust
    fn execute(&self, context: &mut Context, _input: Self::Input) -> HandlerResult<StepDecision> {
        if !RETRY.condition_results(context)?.is_empty() {
            return Ok(StepDecision::go_to(&DoWorkStep, false));
        }
        Ok(StepDecision::force_fail("manual recovery skipped"))
    }
```

### Graceful timeout

Register a Flow timeout handler and start with handler timeout policy/options. The main Step may finish before the deadline; otherwise the handler returns a forced terminal decision. The runnable [FlowGracefulTimeout](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/timeout/flow.rs) configures a 30-second handler method timeout and bounded retries.

## Channel draining

### Internal publication

Fan out the main producer and one consumer. The producer publishes data then moves to a finalizer that publishes a sentinel. The consumer handles one message per execution, loops for data, and completes on the sentinel. The sentinel orders completion after internal publication.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/drain_channels/flow.rs)
<!-- dex-source: examples/rust/src/patterns/drain_channels/flow.rs -->
```rust
        match command {
            SideStepData::Message(value) => {
                context.record_event("drained-internal", value)?;
                Ok(StepDecision::go_to(&SideStep, ()))
            }
            SideStepData::Final => Ok(StepDecision::graceful_complete(())),
        }
```

### External publishing

An RPC can publish while the Flow is open, so no sentinel can prove that no later publisher exists. Drain one item, then use `force_complete_if_channels_empty` to atomically complete only if the queue remains empty; otherwise schedule another drain.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/drain_channels/flow.rs)
<!-- dex-source: examples/rust/src/patterns/drain_channels/flow.rs -->
```rust
        Ok(StepDecision::force_complete_if_channels_empty(
            String::new(),
            StepMovement::to(&DrainChannel, String::new()),
            [EXTERNAL_QUEUE.when_empty()],
        ))
```

## Interruptible execution

Use an RPC to write a durable interrupt Attribute. Parallel or looping Steps check it at safe boundaries and complete cleanly. Do not rely only on an in-memory cancellation token. The full runnable source is [InterruptibleFlow](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/interruptible/flow.rs); it demonstrates two timer-paced branches and identity-aware logging.

## Responsive update

### Wait for Step completion

Use this when one named Step commits the result a caller needs while background work continues. Start the Flow, then wait for `StepExecutionId` with a controller deadline. The Step must write durable state before returning its decision.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/wait_for_step_completion/controller.rs)
<!-- dex-source: examples/rust/src/patterns/wait_for_step_completion/controller.rs -->
```rust
        let run_id = client.start_flow(&flow, &flow_id, input)?;
        client.wait_for_step_completion(
            &flow_id,
            WaitForStepCompletionFlow::persisted_step(),
            Duration::from_secs(300),
        )?;
```

### Wait for Attribute equal

Use this when readiness is a durable primitive business value rather than one Step's completion. It supports string, Boolean, and numeric singleton Attributes. Keep richer data elsewhere and wait on a compact readiness Attribute.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/products/engagement/controller.rs)
<!-- dex-source: examples/rust/src/products/engagement/controller.rs -->
```rust
        client.wait_for_attribute_equal(
            &flow_id,
            &EMPLOYER_ID,
            employer_id,
            Duration::from_secs(15),
        )?;
```

### Wait and Stream

Use a Stream for ordered incremental updates. The caller passes its last resume token to a long-polling read and persists the returned token before asking again. Stream messages are not a final Flow result.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/stream/controller.rs)
<!-- dex-source: examples/rust/src/primitives/stream/controller.rs -->
```rust
        client
            .read_stream_with_timeout(
                &query.workflow_id,
                &PROGRESS,
                &query.resume_token,
                Duration::from_secs(20),
            )
```

## Entity Store

Use a Step-less, RPC-driven Flow as a durable entity when each entity ID maps naturally to one Flow ID. Initialize typed Attributes, synchronize selected values to an Attribute Store, validate every replacement, and expose read/update/clear RPCs. The runnable [UserProfileFlow](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/patterns/entity_store/flow.rs) covers strings, Boolean, integers, floats, time-as-string, and a nested serde object. Empty `StepList` is intentional; RPCs own the lifecycle.

## Coverage map

| Pattern family | Runnable Rust implementation |
| --- | --- |
| Parallel Steps | `examples/rust/src/patterns/parallel/parallel_step_flows.rs` |
| Parallel SubFlows | `examples/rust/src/patterns/parallel_subflows/flow.rs` |
| Polling | `examples/rust/src/patterns/polling/flow.rs` |
| Cron, reminder, inactivity | `examples/rust/src/patterns/cron/flow.rs`, `reminders/flow.rs`, `inactiveness_tracker/flow.rs` |
| Execute/manual/timeout recovery | `recovery/flow.rs`, `intervention/flow.rs`, `timeout/flow.rs` |
| WaitFor recovery | `examples/rust/src/primitives/proceed_on_wait_failure/flow.rs` |
| Channel draining | `examples/rust/src/patterns/drain_channels/flow.rs` |
| Interruptible | `examples/rust/src/patterns/interruptible/flow.rs` |
| Responsive update | `wait_for_step_completion/controller.rs`, `products/engagement/controller.rs`, `primitives/stream/controller.rs` |
| Entity Store | `examples/rust/src/patterns/entity_store/flow.rs` |
