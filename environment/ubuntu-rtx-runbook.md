# Ubuntu RTX runbook

The Ubuntu node is an execution environment, not the canonical source tree.
Source changes are made on the Mac, tested locally, and synchronized to a
versioned directory on the node. Raw GPU artefacts are synchronized back to
the Mac before analysis or manuscript use.

## Current verified host

- Ubuntu 22.04.5 LTS
- NVIDIA GeForce RTX 4090 D, 24 GB
- NVIDIA driver 560.35.05
- Isaac Sim 4.2.0 at
  `/home/seu-zheng/.local/share/ov/pkg/isaac-sim-4.2.0`

## Stage-loading smoke test

Run from the synchronized project root:

```bash
ISAAC_ROOT=/home/seu-zheng/.local/share/ov/pkg/isaac-sim-4.2.0
"${ISAAC_ROOT}/python.sh" scripts/isaac_stage_smoke.py \
  --stage generated/local-pipeline/usd/pin_insertion/building_root.usda \
  --output generated/rtx/RTX-SMOKE-0001.json \
  --steps 60
```

The test verifies only that the composed stage opens and can be advanced by
PhysX. It does not establish motion-planning or humanoid assembly success.

## Paired batch

The paired batch randomizes the order of task-activated and all-loaded
conditions within each repeat and launches a fresh Isaac process for every
observation:

```bash
python3 scripts/run_isaac_stage_batch.py \
  --project-root . \
  --isaac-root /home/seu-zheng/.local/share/ov/pkg/isaac-sim-4.2.0 \
  --output-dir generated/rtx/stage-batch-v1 \
  --repeats 5 \
  --steps 240
```

## Data return

Only raw run artefacts are copied back:

```bash
rsync -av school-gpu:~/research/construction-scene-ready/generated/rtx/ \
  generated/rtx/
```

The Mac remains the source of truth for statistics, figures, tables, and the
LaTeX manuscript.
