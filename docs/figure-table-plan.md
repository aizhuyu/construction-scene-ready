# Publication figure and table plan

This document freezes the visual evidence plan for the
**ConstructionSceneReady** manuscript. Placeholders are intentionally included
in the LaTeX source before final experiments so that the analysis is designed
to answer the paper's claims rather than the manuscript being illustrated
after the fact.

## 1. Production standard

- Prepare every diagram as an editable SVG master and submit vector artwork as
  embedded-font PDF or EPS.
- Use 90 mm for single-column, 140 mm for intermediate-width, and 190 mm for
  double-column artwork. The current method figures are planned at 190 mm.
- Use 7 pt final-size text for normal labels and never below 6 pt for
  subscripts or superscripts.
- Keep vector line weights between 0.1 and 1.5 pt at final size. The house
  default is 0.75 pt for structural lines and 1.1 pt for emphasized flows.
- Use RGB for colour figures. Use a colour-blind-safe palette and encode method
  identity with marker shape, line style, or direct labels as well as colour.
- Rasterize only true simulator or photographic content. Use 300 dpi for
  continuous-tone images, 500 dpi for mixed image/line artwork, and 1000 dpi
  for pure raster line art.
- Data figures must be generated from versioned CSV/Parquet files using Python
  or R. No chart value may be manually placed in a drawing program.
- Simulation panels must be true runtime captures. Generative image models may
  not create or alter scientific evidence. AI may assist with layout drafting,
  code, or visual QA, but the editable source and evidence provenance are
  retained.
- Captions must be self-contained and state what is encoded, the comparison
  unit, uncertainty representation, and any relevant sample size.
- Tables remain editable text, use `booktabs`, omit vertical rules and
  background shading, define all abbreviations, and do not duplicate values
  already readable in a figure.

## 2. Visual language

| Meaning | Encoding |
|---|---|
| IFC / source engineering information | blue-grey |
| Construction-scene intermediate representation | teal |
| OpenUSD layers and payloads | blue |
| Deterministic validation | amber |
| Permitted repair | green |
| Escalation / unsafe or unsupported condition | vermilion |
| Runtime and measured outcomes | dark violet |

Method names keep the same order in every result figure: direct conversion,
fixed-rule conversion, unconstrained agent, and ConstructionSceneReady. Use
short, direct labels and sentence case. Icons are secondary to explicit text.

## 3. Graphical abstract

**Purpose.** Communicate one claim: construction information becomes a usable
robot world only after task-specific composition, deterministic scene
validation, and auditable repair.

**Composition.** Three horizontal regions:

1. IFC, task, and humanoid inputs.
2. Multi-scale scene compilation plus deterministic validation.
3. Pass to runtime, bounded repair, or escalation, ending in measured task
   success.

**Do not include.** Literature comparisons, a full rule taxonomy, invented
results, or more than one humanoid screenshot.

**Output.** Separate editable SVG and submission PDF/EPS. It is not numbered in
the manuscript.

## 4. Main figures

### Figure 1 — Asset readiness is not scene readiness

- **Scientific role:** establishes the problem unit and explains why existing
  asset checks are insufficient.
- **Panels:** IFC design model; individually valid assets; four composition
  defects; task-scene contract.
- **Evidence:** real fixture identifiers and validator fault examples.
- **Drawing method:** deterministic SVG diagram. No simulator render required.
- **Acceptance:** every shown defect maps to a versioned rule and later
  benchmark fault; readable at 190 mm and in greyscale.

### Figure 2 — Overall architecture

- **Scientific role:** exposes module boundaries, information products, and the
  separation between deterministic decisions and agentic assistance.
- **Panels:** inputs; typed IR; multi-scale USD; validator; repair/escalation;
  CPU and RTX outcomes.
- **Evidence:** actual CLI/module names and generated file types.
- **Drawing method:** SVG generated from a versioned figure specification.
- **Acceptance:** no crossing primary arrows; all data artefacts labelled;
  modules correspond one-to-one with implemented packages.

### Figure 3 — Typed intermediate representation and provenance

- **Scientific role:** formalizes the semantic contribution.
- **Content:** eight entity types, typed relations, and one enlarged provenance
  tuple.
- **Evidence:** schema and JSON fixture.
- **Drawing method:** Graphviz/D2 or direct SVG followed by Inkscape QA.
- **Acceptance:** cardinality and relation direction match the schema;
  provenance is attached to a critical property.

### Figure 4 — Task-activated multi-scale OpenUSD composition

- **Scientific role:** demonstrates how building-scale and interaction-scale
  fidelity coexist.
- **Panels:** global, work-zone, interaction, and USD composition tree; small
  measured resource inset.
- **Evidence:** true generated USDA layers and final RTX logs.
- **Drawing method:** vector composition diagram plus unaltered scene
  thumbnails; hybrid PDF.
- **Acceptance:** same GUID traceable across panels; global geometry is visibly
  coarser; resource inset is script-generated.

### Figure 5 — Scene contract and validator-grounded repair

- **Scientific role:** explains the safety and audit boundary of the agent.
- **Content:** rule families; typed diagnostic; allowed-tool repair loop; pass
  and escalation examples.
- **Evidence:** rule registry, diagnostic schema, tool registry, audit log.
- **Drawing method:** vector state/flow diagram.
- **Acceptance:** the agent never appears as the final arbiter; unsupported
  friction is shown as escalation, not automatic repair.

### Figure 6 — Benchmark design

- **Scientific role:** establishes coverage and guards against cherry-picking.
- **Panels:** three tasks, three embodiment levels, six fault families,
  partitions, and four methods.
- **Evidence:** parameterized IFC fixtures, partition manifest, fault taxonomy.
- **Drawing method:** true scene renders arranged inside a vector framework.
- **Acceptance:** development, test, and challenge sets are clearly distinct;
  planned task levels are not portrayed as completed outcomes.

### Figure 7 — Detection and repair performance

- **Scientific role:** answers whether the proposed validator and constrained
  repair improve reliability.
- **Panels:** fault-family recall/F1 with 95% intervals; valid/incorrect/
  escalated outcomes; iterations and time.
- **Evidence file:** `data/results/detection_repair.csv`.
- **Drawing method:** Python; point/forest plots and compact distribution plots.
- **Acceptance:** denominators and confidence intervals shown; colour not the
  sole grouping cue; values tested against the result CSV.

### Figure 8 — Efficiency and downstream task consequence

- **Scientific role:** connects multi-scale compilation and readiness quality
  to operational outcomes.
- **Panels:** prim/memory/load-time comparison; readiness--success logistic
  relationship; failure-cause decomposition.
- **Evidence files:** `data/results/resource_efficiency.csv` and
  `data/results/task_outcomes.csv`.
- **Drawing method:** Python; paired dots, intervals, regression curve and
  compact composition plot.
- **Acceptance:** uncertainty band and observation counts shown; causal
  language avoided unless supported by design; failure causes are mutually
  exclusive or their overlap is disclosed.

### Figure 9 — Auditable humanoid case

- **Scientific role:** makes the quantitative pipeline inspectable.
- **Panels:** IFC/task, invalid scene, diagnostic, repair record, G1 execution,
  completion; plus one escalation example.
- **Evidence:** held-out case artefacts and true Isaac Sim frames.
- **Drawing method:** fixed-camera simulator capture with SVG annotations;
  500-dpi hybrid PDF.
- **Acceptance:** no scene detail is generated or cosmetically removed; frame
  sequence, rule identifier, property provenance, and outcome record agree.

## 5. Main tables

### Table 1 — Literature comparison

Compares the nearest BIM--robotics, physics-ready, multi-scale, validation,
provenance, agent-repair, and runtime-evaluation studies. A cell is marked only
when the capability is a substantive method or evaluation.

### Table 2 — Construction-scene readiness contract

Lists contract category, required evidence, deterministic check, severity, and
task consequence. The full rule catalogue belongs in Supplementary Table S1.

### Table 3 — Benchmark composition

Lists scenario parameterization, embodiment levels, partition counts, and
primary outcomes. Counts must be generated from the frozen partition manifest.

### Table 4 — Baselines and ablations

Freezes each method's representation, validation access, provenance, and
repair authority.

### Table 5 — Detection and repair outcomes

Reports precision, recall, critical recall, valid repair, incorrect repair,
escalation, and runtime. Values are imported from
`data/results/detection_repair.csv`.

### Table 6 — Runtime resources and task outcomes

Reports active prims, peak memory, load time, planning, grasp, alignment,
insertion, and complete-task success with explicit denominators and 95%
confidence intervals.

### Table 7 — Ablation and sensitivity

Reports deltas after removing provenance, task validation, task-activated
layers, agentic tool selection, or typed diagnostics. Statistical tests are
paired and multiplicity correction is disclosed.

## 6. Supplementary visual evidence

- **Figure S1 / Table S1:** full rule taxonomy, version, severity, evidence,
  tool permission, unit test, and task consequence.
- **Figure S2:** all fault operators with before/after visual or structural
  examples.
- **Figure S3:** complete diagnostic--tool--audit trace for agent repetitions.
- **Figure S4:** per-scene distributions, not only aggregate means.
- **Figure S5:** additional humanoid task and failure sequences.
- **Table S2:** environment, package, simulator, robot asset, model, prompt,
  decoding, and seed versions.
- **Table S3:** statistical models, assumptions, effect estimates, intervals,
  and corrected p-values.

## 7. Data-to-figure contracts

Every quantitative figure has:

1. a tidy source file with one row per observation;
2. a data dictionary and units;
3. a deterministic plotting script;
4. an editable SVG and submission PDF;
5. an automated check that plotted counts and summary statistics equal the
   analysis output;
6. a caption generated from a versioned text file;
7. a provenance record containing source hashes and software versions.

Recommended result schemas:

```text
detection_repair.csv
case_id, partition, scenario, fault_family, method, seed,
tp, fp, fn, critical_detected, repair_outcome, iterations, time_s

resource_efficiency.csv
case_id, scenario, layer_condition, active_prims, peak_cpu_mb,
peak_gpu_mb, load_time_s, collision_query_ms

task_outcomes.csv
case_id, scenario, task_level, method, readiness_score,
planning_success, grasp_success, alignment_success,
insertion_success, full_task_success, failure_cause
```

## 8. Figure production workflow

1. Freeze the message, panels, fields, and comparison unit in the figure
   specification.
2. Generate or export the evidence from registered code.
3. Produce diagrams from SVG/Graphviz/D2 and result figures from Python/R.
4. Render at final journal size, not at screen size.
5. Run semantic QA and visual QA.
6. Export editable master, submission PDF/EPS, and a preview.
7. Record data and source hashes in the figure provenance manifest.

AI-assisted generation is acceptable for drafting layout or code, but it does
not replace deterministic rendering, evidence checks, or author review.
