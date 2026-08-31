# Live Run Protocol v0.1

## Goal

Produce the first reproducible B0–B4 comparison without changing the model, dataset, tool surface, or run parameters between systems.

## Prompt pairing

To isolate CIEL's contribution:

- B1 and B3 use the exact same bytes from `prompts/b1_b3_structured.txt`.
- B2 and B4 use the exact same bytes from `prompts/b2_b4_research_structured.txt`.
- B0 uses `prompts/b0_direct.txt` because it intentionally lacks the structured-output control.

`audit-manifests` fails closed if either ablation pair has prompt drift.

## Run sequence

For each replicate:

1. freeze the benchmark commit after all run code is committed;
2. freeze exact dataset bytes;
3. choose one model/provider and one parameter object for all B0–B4 systems;
4. generate five run manifests with `make-manifest`;
5. capture raw predictions before scoring;
6. score captured predictions with strict system contracts for B1–B4;
7. audit all five manifests;
8. compare the scored run directories;
9. preserve raw predictions, manifests, receipts, and aggregate outputs.

## Component pins

Use `COMPONENT_PINS_V0_1.json` as the current candidate integration set. If any component moves, create a new pin receipt rather than silently updating a run.

## Result labels

`EXPLORATORY`: model runs are real and manifests are reproducible, but one or more pinned component full-suite gates remain unverified.

`REPORTABLE_V0_1`: B0–B4 manifests pass comparability audit, all captures pass strict receipt contracts, and the exact pinned component suites have passed.

Metric sanity controls are never reported as B0–B4 model results.
