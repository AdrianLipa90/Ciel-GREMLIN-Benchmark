# CIEL × GREMLIN Integration Pins

Observed for benchmark integration on 2026-08-30. These are candidate component pins for the first live v0.1 run; each actual run must copy the exact used SHAs into its `RunManifest.component_commits`.

## GREMLIN

Repository: `AdrianLipa90/GREMLIN`  
Branch: `feat/gremlin-research-engine-v0.1`  
Observed HEAD: `3693b933b67213815d1632a93bf3cae11175fd51`

The research surface exposes candidate/evidence acquisition and specialist audit receipts while retaining bounded authority. B2/B4 must preserve the native GREMLIN receipt under `receipts.gremlin`.

## CIELingo producer

Repository: `AdrianLipa90/cielingo-canon`  
Branch: `feat/relation-event-hypergraph-v0.1`  
Observed HEAD: `9c4f4f8a5b230d81605b9c3a9078d216f24cd942`

This stack contains CasePortFrame → OperatorSignature → MeaningRoleMultimap → RelationHypergraph transport.

## CIEL semantic consumer

Repository: `AdrianLipa90/Ciel-Semantic-Model-`

Stable typed-signature parent branch: `feat/operator-signature-bridge-v0.1`  
Observed HEAD: `6a23a5a6ec29cc04715bc2cd05be0d52eea7f0b1`

Stacked relation-hypergraph branch: `feat/relation-event-hypergraph-bridge-v0.1`  
Observed HEAD: `278d0c4645ab6a5c369aff261f7c1bad0499903a`

### Admission gate for B3/B4

The relation-hypergraph stacked branch is not yet admitted as the benchmark pin because `tests/test_relation_hypergraph_bridge.py` is absent at the observed HEAD. Before the first B3/B4 live run, restore the bridge test fixture, synchronize the exact signature-mirror tests from the parent branch, and run deterministic validation.

Until that gate passes, no B3/B4 live comparative result should be reported as a completed v0.1 benchmark.
