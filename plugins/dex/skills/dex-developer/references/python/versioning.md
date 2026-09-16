# Versioning Python applications

## Check first

```bash
python -c 'import importlib.metadata; print(importlib.metadata.version("dex-python-sdk"))'
uv tree | grep -i dex
```

Use the package name recorded by the project's lockfile if distribution metadata differs. Installed source/declared dependency is authoritative; this handbook is pinned evidence.

## Open Flows

Preserve Flow type, Step type names, schema names/types, and decodable models for runs that can resume on new code. Renaming a Python class can change its Step identity. Add a new Step/Flow for incompatible behavior and keep old definitions registered until runs drain.

Dataclass field additions with defaults are safer than removals/type changes. Never repurpose string/enum meanings. Keep module import paths available if registry/bootstrap imports them.

## Rollout and policies

Deploy a Worker capable of old/new runs, then update Worker target deliberately. Choose ID reuse and ignore-already-started as business semantics. Test active and closed prior IDs.

[Pinned runnable source](https://github.com/superdurable/dex/blob/4c18c7d04135053c6a3f387a8f411c918f7ba803/examples/python/dex_examples/primitives/flow/controller.py)
<!-- dex-source: examples/python/dex_examples/primitives/flow/controller.py -->
```python
async def reroute_active_flow(client: AsyncClient, flow_id: str) -> None:
    await client.update_flow_config(
        flow_id,
        FlowConfig(worker_target=WorkerTarget("worker-canary:8803")),
    )
```

Upgrade-test open runs across Worker replacement at map, Channel, Timer, RPC, retry, and timeout-handler boundaries. Run both async and sync surfaces if both are deployed.
