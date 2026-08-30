# CIEL × GREMLIN Integration Pins

Observed for benchmark integration on 2026-08-30. Every actual run must copy the exact used SHAs into `RunManifest.component_commits`.

## GREMLIN

Repository: `AdrianLipa90/GREMLIN`  
Branch: `feat/gremlin-research-engine-v0.1`  
Candidate pin: `3693b933b67213815d1632a93bf3cae11175fd51`

GREMLIN remains the candidate/evidence/adversarial research layer. B2/B4 preserve its native research receipt under `receipts.gremlin`; that receipt does not grant execution authority.

## CIELingo producer

Repository: `AdrianLipa90/cielingo-canon`  
Branch: `feat/relation-event-hypergraph-v0.1`  
Candidate pin: `1a42123a44df641e41207ced919714d32dd46780`  
Stacked draft PR: `#18`, base `feat/operator-signatures-v0.1`, mergeable.

The producer carries CasePortFrame → OperatorSignature → MeaningRoleMultimap → RelationHypergraph. The current stack includes an adversarial missing-port gate in which the graph commitment is recomputed after removing the GIVES ACC port; validation must still fail on signature arity/port-set. It also pins the `SentenceEquation` tail ABI as `notes, role_multimap, relation_hypergraph`.

## CIEL semantic consumer

Repository: `AdrianLipa90/Ciel-Semantic-Model-`  
Branch: `feat/relation-event-hypergraph-bridge-v0.1`  
Candidate pin: `bc4571d6485dbd8c85876ba2c4739fb3fa290fc8`  
Stacked draft PR: `#27`, base `feat/operator-signature-bridge-v0.1`, mergeable.

The stack is synchronized with the typed-signature parent at `6a23a5a6ec29cc04715bc2cd05be0d52eea7f0b1`. Its effective diff versus the parent is limited to the relation-hypergraph bridge, its adversarial test fixture, and cross-repo metadata.

Independent structural GIVES harness: PASS for six structural cases (valid full graph, missing port, UniversalRole tamper, relation-family tamper, forged signature SHA, raw commitment tamper).

## Admission status

An exploratory B0–B4 run may use the candidate pins above if the manifests label the exact commits.

A result must not be called the completed/reportable v0.1 benchmark until the full component repository suites for the pinned CIELingo and CIEL Semantic heads have executed successfully. No hosted GitHub Actions workflow run was observed for the current heads, so the structural checks above are reported separately from full-suite validation.
