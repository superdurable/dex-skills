# Rust primitives

Read the core primitives guide first for product semantics. This page records the Rust SDK shapes at the pinned baseline.

## Flow, Step, and Wait

`Flow::StartInput` is the input accepted by `Client::start_flow`. `steps` returns the closed Step graph. A Step's WaitFor phase decides durable readiness; Execute performs side effects and returns the next graph movement. `Wait::until`, `any_of`, `all_of`, and `any_combination_of` compose Conditions. `Wait::skip_immediately` bypasses waiting.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/wait_types/flow.rs)
<!-- dex-source: examples/rust/src/primitives/wait_types/flow.rs -->
```rust
    fn wait_for(&self, _context: &mut Context, input: Self::Input) -> HandlerResult<Wait> {
        let timeout = Duration::from_secs(input.timeout_seconds.max(0) as u64);
        match input.mode.as_str() {
            "any" => Ok(Wait::any_of([
                SIGNAL_A_CHANNEL.for_one().with_id("signal"),
                Timer::by_duration(timeout).with_id("timeout"),
            ])),
            "all" => Ok(Wait::all_of([
                SIGNAL_A_CHANNEL.for_one().with_id("signal-a"),
                SIGNAL_B_CHANNEL.for_one().with_id("signal-b"),
            ])),
            "combo" => Ok(Wait::any_combination_of([
                ConditionCombination::all_of([
                    SIGNAL_A_CHANNEL.for_one().with_id("signal-a"),
                    Timer::by_duration(timeout).with_id("timeout"),
                ]),
                ConditionCombination::all_of([SIGNAL_B_CHANNEL.for_one().with_id("signal-b")]),
            ])),
            _ => Err(HandlerError::new(
                "WaitTypes",
                format!("unknown wait mode {}", input.mode),
            )),
        }
    }
```

Use condition IDs when Execute must distinguish multiple timers or conditions. Read typed condition results from `Context`; do not infer a winner from elapsed wall time.

## Step decisions

- `StepDecision::go_to` schedules one next Step.
- `go_to_many` fans out movements.
- `graceful_complete` contributes a terminal output after siblings settle.
- `force_complete` ends the Flow immediately.
- `force_fail` terminally fails it.
- `dead_end` ends only that branch.
- cancellation modifiers cancel a sibling Step type or a selected execution.

Use `StepMovement::to_with_options` when one transition needs different options without changing the Step's defaults. Never choose force completion merely to make a test finish; it changes sibling and outstanding-work semantics.

## Attributes and maps

An `Attribute<T>` stores one typed durable value. `AttributeMap<T>` stores independently addressable instances. Both belong in `PersistenceSchema`. Indexed attributes support Flow search; `sync_to_attribute_store` projects values into an Attribute Store configured by `FlowConfig`.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/attribute/flow.rs)
<!-- dex-source: examples/rust/src/primitives/attribute/flow.rs -->
```rust
static STATUS: LazyLock<Attribute<String>> = LazyLock::new(|| {
    Attribute::new("primitive-attribute-status")
        .indexed(AttributeIndex::keyword().with_key("OrderStatus"))
});
static EMAIL: LazyLock<Attribute<String>> =
    LazyLock::new(|| Attribute::new("primitive-attribute-email").sync_to_attribute_store());

pub fn attribute_store_config() -> FlowConfig {
    FlowConfig::new().attribute_store_names(vec!["profiles".to_owned()])
}
```

Call `get`, `set`, or `clear` through `&mut Context`. Load only the map instances needed by a handler, and lock every attribute whose read-modify-write invariant must be serialized.

## Channels and maps

Channels are durable message queues. `for_one` and `for_n` create wait Conditions; `publish` appends; `pending_messages`, `find_pending_message`, and `delete` support explicit queue management. A `ChannelMap<T>` partitions queues by instance key. Declare the definition before attaching instance loads.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/channel/flow.rs)
<!-- dex-source: examples/rust/src/primitives/channel/flow.rs -->
```rust
    fn rpcs(&self) -> RpcList<Self> {
        RpcList::new()
            .procedure_without_input(CHANNEL_APPROVE, Self::approve)
            .procedure(
                CHANNEL_MOVE.is_transactional().load_channel(&QUEUED),
                Self::move_message,
            )
    }
```

Deleting and republishing is a transaction only when the RPC requests transactional execution. A Channel wait does not itself guarantee that a later Execute mutation is atomic with publication.

## RPC

Define an `Rpc<Input, Output>` with a stable logical name, register it in `Flow::rpcs`, and expose a handler taking `&mut Context`. Use `procedure_without_input` for unit input and a function registration when there is a typed response. An `RpcResult` may return a value and a `StepMovement`.

RPCs can declare locks, timeout, transactions, and selective loads. Treat an RPC as a durable command/query boundary, not an arbitrary escape hatch into Worker memory.

## Stream

`Stream<T>` is append-oriented output. Give it a maximum payload size and add it to `PersistenceSchema`. Text output can be buffered to avoid one remote write per fragment.

[Runnable source](https://github.com/superdurable/dex/blob/c498d430518008347222a8f1ef027215fd894ac2/examples/rust/src/primitives/stream/flow.rs)
<!-- dex-source: examples/rust/src/primitives/stream/flow.rs -->
```rust
        let progress = PROGRESS.buffered_text_with_options(
            context,
            BufferedTextStreamOptions::new(Duration::from_millis(500), 16 * 1024),
        )?;
        progress.write(format!("Rendering preview for {input}"))?;
        progress.write(format!("Preview ready for {input}"))?;
```

Buffered writes are asynchronous; use them for progress-like output, not as the only proof that a business mutation committed.

## Timer and SubFlow

`Timer::by_duration` creates a durable relative timer. Compose it with Channels for reminders, inactivity races, and deadlines. `SubFlow::run` starts a child and returns a Condition. `SubFlowOptions` controls timeout and timeout policy. After the wait, read the typed `SubFlow::condition_result`, outputs, and Flow IDs from Context.

## Client

`Client` starts, stops, searches, and inspects Flows; invokes RPCs; publishes Channels; reads Channels and Attributes; waits for Flow or Step completion; and retrieves Stream output. Controllers should map `SdkError` explicitly and move blocking client calls off async executor threads. Use a unique Flow ID for each test or logical entity, and a stable request ID when retrying the same command.
