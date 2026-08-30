# CIEL × GREMLIN Integration Pins

Observed for benchmark integration on 2026-08-30. Every actual run copies the exact used SHAs into `RunManifest.component_commits`.

## GREMLIN

Repository: `AdrianLipa90/GREMLIN`  
Branch: `feat/benchmark-supplied-evidence-v0.1`  
Candidate pin: `7b80db8dd7a553c77616427a91bade608e12b968`  
Draft PR: `#44`, based directly on current GREMLIN `main`.

The benchmark lane accepts caller-supplied task evidence, reuses native OWL/SPIDER/MOLE/HOUND handlers and BELZEBUB synthesis, and applies the existing relational case-frame enrichment. Existing web research remains unchanged. Authority remains candidate-only.

Hosted GREMLIN MCP/relational CI: **PASS — 43 tests** including `test_gremlin_supplied_evidence_research_v01.py`.

## CIELingo producer

Repository: `AdrianLipa90/cielingo-canon`  
Branch: `feat/relation-event-hypergraph-v0.1`  
Candidate pin: `43375f58d46ca99ed6e8536fc65ceb02816f5c3e`  
Stacked draft PR: `#18`, base `feat/operator-signatures-v0.1`, mergeable.

The producer carries CasePortFrame → OperatorSignature → MeaningRoleMultimap → RelationHypergraph. Structural validation covers exact GIVES arity/ports, implicit subject, signature commitments, anti-INSTRUMENT semantics and additive SentenceEquation transport.

Hosted private-repo CI was triggered on this stacked base but the failing matrix job contained **zero executed steps** and no pytest log. Status is therefore `INFRA_FAILURE_BEFORE_STEPS`, not a code/test FAIL.

## CIEL semantic consumer

Repository: `AdrianLipa90/Ciel-Semantic-Model-`  
Branch: `feat/relation-event-hypergraph-bridge-v0.1`  
Candidate pin: `67157523badc1460eefc18f75b75ff20500dcbc3`  
Stacked draft PR: `#27`, base `feat/operator-signature-bridge-v0.1`, mergeable.

Independent structural GIVES harness: PASS for valid full graph plus missing-port, UniversalRole tamper, relation-family tamper, forged-signature and raw-commitment adversarial cases.

Hosted private-repo CI likewise terminated before any step (`steps=[]`), so it is recorded as infrastructure failure rather than code failure.

## Admission status

Exploratory B0–B4 runs may use these exact candidate pins. `REPORTABLE_V0_1` still requires an executed full suite for both private CIEL components or an equivalent independently reproducible full-suite execution.
