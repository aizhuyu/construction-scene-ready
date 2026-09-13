# Baseline and ablation protocol

This document freezes the comparison before any RTX or language-model results
are collected. All methods receive the same source IFC fixture, task
specification, injected fault, and trusted evidence bundle. They are evaluated
on the same train/development/test split. No method may inspect fault labels or
the pristine target scene at evaluation time.

## B0: direct conversion

- Input: IFC fixture and task configuration.
- Process: compile once without Construction Scene Readiness rules.
- Repair: none.
- Purpose: isolate the value of format conversion alone.
- Report: compilation success, generic USD/asset validation, active working
  set, and downstream task outcome.

## B1: deterministic conversion and fixed repair

- Input: the same IFC fixture and task configuration.
- Process: deterministic compiler and the rule set available before test
  faults are generated.
- Repair: one fixed repair action per known rule; no language model.
- Purpose: establish how far a conventional rule-based system can go.
- Restriction: rules and repair mapping are frozen before the test split.

## B2: unconstrained agentic repair

- Input: candidate scene, natural-language validator report, and general file
  editing tools.
- Process: a language-model agent may inspect and modify the candidate scene.
- Repair: unrestricted scene mutation, subject only to file-system safety.
- Purpose: test whether an agent that can make plausible edits but lacks
  engineering authority produces incorrect or unsupported repairs.
- Acceptance: the agent's own completion claim is recorded but never treated as
  ground truth.

## B3: validator-grounded agentic repair

- Input: candidate scene, typed rule findings, permitted tools, and trusted
  evidence references.
- Process: a language-model agent selects only from the approved repair-tool
  registry.
- Repair: every mutation records tool, target, before/after values, evidence
  source, and confidence.
- Acceptance: independent deterministic revalidation; unsupported parameters
  are escalated rather than invented.

## Ablations

- A1: B3 without provenance checks.
- A2: B3 without task-level rules.
- A3: B3 with all USD layers loaded rather than task-activated payloads.
- A4: B3 without agent selection, applying every safe repair in a fixed order.
- A5: B3 using prose diagnostics instead of typed findings.

## Fault and scene splits

- Development faults: used to implement and debug rules and tools.
- Test faults: held-out parameter values and compound combinations from known
  fault families.
- Challenge faults: at least one fault family withheld from repair-tool
  development to measure escalation and unsafe generalization.
- Scene split: base geometry and component dimensions must differ between
  development and test fixtures.

## Mandatory outputs per run

- method and software version;
- source-scene and fault IDs;
- expected and observed rule IDs;
- root and consequential findings;
- mutation audit;
- validation and repair time;
- language-model identifier, decoding settings, tokens, and cost when used;
- pass, rejection, or human-escalation status;
- active USD prim count and memory footprint;
- motion-planning and assembly outcome when RTX execution is enabled.

## Statistical comparison

- Detection: precision, recall, F1, and critical-fault recall with bootstrap
  95% confidence intervals.
- Repair: final valid-scene rate, incorrect-repair rate, escalation rate, and
  repair iterations.
- Paired binary outcomes: McNemar test.
- Paired time, memory, and iteration outcomes: Wilcoxon signed-rank test.
- Task-success association: logistic regression using readiness score and
  critical-rule failures as predictors.
- Repeated language-model runs: at least five seeds per test case; report both
  per-run and majority outcomes.

## Reporting rule

CPU pilot values are labelled as implementation checks. B2 and B3 language
model results are not reported until the model, prompt, tool registry, repeat
count, and cost log have been frozen. Humanoid task claims are not reported
until the corresponding RTX/Isaac Sim run artefacts are available.
