# ConstructionSceneReady research starter

This folder is the local, CPU-first starting point for an *Automation in
Construction* paper:

> **ConstructionSceneReady: Multi-scale IFC-to-OpenUSD compilation and
> scene-level validation for humanoid robotic assembly**

The project deliberately separates:

- **local/CPU research**: IFC semantics, the scene contract, static validators,
  fault injection, constrained repair, statistics, and manuscript writing;
- **later RTX research**: Isaac Sim loading, PhysX runtime tests, Unitree G1
  whole-body tasks, sensors, and task-level benchmark runs.

## What is ready now

- `research-plan-zh.md`: the frozen Chinese research plan;
- `docs/literature-matrix.csv`: a 55-source novelty and scope audit plus the
  planned-study comparison row;
- `docs/reference-audit.csv`: Crossref verification of all DOI-bearing
  bibliography records;
- `docs/novelty-audit-2026-07-27.md`: current claim boundaries and the
  defensible combined contribution;
- `docs/fault-taxonomy.csv`: the frozen local fault taxonomy;
- `docs/scene-readiness-rules.csv`: the generated registry of 30 executable
  rules, severities, evidence requirements, and repair authority;
- `docs/baseline-protocol.md`: baseline, ablation, split, and reporting rules;
- `paper/`: an Elsevier `elsarticle` manuscript, title page, highlights, and
  section files;
- `src/`: an IFC4.3 fixture generator, IFC-to-scene compiler, multi-layer
  OpenUSD compiler, canonical CEWG builder and schema, fault injector, and
  deterministic scene validator;
- `examples/`: one passing and one intentionally faulty scene;
- `tests/`: local unit and integration tests;
- `generated/local-pipeline/`: reproducible IFC, ground-truth, scene, USD,
  fault, and validation-report artefacts.

## Run the local prototype

```bash
make test
make validate
make validate-faulty
make local-pipeline
```

The faulty example is expected to exit non-zero and print structured rule
violations.

## Compile the AIC manuscript

```bash
make paper
```

The PDF is generated at `paper/manuscript.pdf`. The manuscript uses the
official Elsevier `elsarticle` class and numbered Elsevier bibliography style.
It is intentionally anonymous; author details are kept in
`paper/title-page.tex`.

## Optional local scientific dependencies

The initial validator uses only the Python standard library. When beginning
IFC and OpenUSD implementation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[ifc,analysis]"
python -m pip install usd-core
```

Keep NVIDIA/Isaac dependencies out of the Mac environment. They belong in a
separate, version-locked Ubuntu RTX environment.

`make local-pipeline` requires the optional IFC and OpenUSD dependencies. It
generates three parameterized IFC4.3 assembly scenes and compiles each one into
`global_navigation.usda`, work-zone payloads, interaction layers, and a
composed `building_root.usda`.

## Current local milestone

The repository currently demonstrates:

1. three IFC4.3 assembly fixtures compiled into an intermediate scene model;
2. a canonical typed CEWG with closed cross-entity relations and JSON Schema;
3. deterministic, paired scene variants with source-preservation ground truth;
4. thirty deterministic construction-scene rules;
5. thirty single faults and five compound faults with machine-readable
   ground truth;
6. global, work-zone, and interaction OpenUSD layers using references and
   payloads;
7. one-command reports recording the rules triggered by every injected fault;
8. twenty-nine whitelisted repair tools with mutation provenance and mandatory
   re-validation;
9. a 105-case CPU implementation check saved to
   `generated/local-pipeline/reports/cpu-benchmark.json`.

The next gate is to run the frozen fixed-rule and language-model baselines,
then execute paired scene-loading, planning, and assembly tests on an Ubuntu
RTX node.

The Ubuntu execution procedure and Mac return path are documented in
`environment/ubuntu-rtx-runbook.md`.

The source artefacts are also checked for byte-level reproducibility. Random
IFC identifiers, header timestamps, unordered IFC relationship sets, and
machine-specific source paths are normalized before comparison. Runtime
measurements and output-directory paths are excluded from this byte comparison
and are evaluated separately.
