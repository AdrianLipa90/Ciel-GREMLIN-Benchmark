# CIEL × GREMLIN Integration Pins

Observed for benchmark integration on 2026-08-30. Every actual run copies the exact used SHAs into `RunManifest.component_commits`.

## GREMLIN

Repository: `AdrianLipa90/GREMLIN`  
Branch: `feat/benchmark-supplied-evidence-v0.1`  
Candidate pin: `69f4670f1b4c618a964d2e246987aa8de6d61b09`  
Draft PR: `#44`, based directly on GREMLIN `main`.

The benchmark lane accepts caller-supplied task evidence, reuses native OWL/SPIDER/MOLE/HOUND handlers and BELZEBUB synthesis, and applies the existing relational case-frame enrichment. Existing web research remains unchanged. Authority remains candidate-only.

Hosted validation on the exact pinned head:
- MCP/relational/supplied-evidence suite: **43/43 PASS**
- benchmark receipt generation: **60/60 PASS**
- receipt bundle SHA-256: `c6167a581d76e3c52376cbef91fc4b1779eb430d3bc5fa8250cf7c7f2e7393f7`
- workflow run: `33299763706`
- artifact ID: `9728536601`
- artifact ZIP SHA-256: `07b7becdc38c5854c38cbcfd9366e706619ab3000b43e61eaae7f036d41c23b0`
- benchmark commit used by the receipt build: `6f4496c451d7ce4935678cc92df49f4e0920cc31`

The generated receipt bundle remains a reproducible Actions artifact. `VALIDATED_ARTIFACTS_V0_1.json` records its immutable provenance; generated receipt bytes are not treated as source code.

## CIELingo producer

Repository: `AdrianLipa90/cielingo-canon`  
Branch: `feat/relation-event-hypergraph-v0.1`  
Candidate pin: `43375f58d46ca99ed6e8536fc65ceb02816f5c3e`  
Stacked draft PR: `#18`, base `feat/operator-signatures-v0.1`, mergeable.

The producer carries CasePortFrame → OperatorSignature → MeaningRoleMultimap → RelationHypergraph. Structural validation covers exact GIVES arity/ports, implicit subject, signature commitments, anti-INSTRUMENT semantics and additive SentenceEquation transport.

Hosted workflow run `33299470285` was retried. The failed/cancelled matrix jobs still contain **zero executed steps** (`steps=null`) and no pytest log. Status remains `INFRA_FAILURE_BEFORE_STEPS`, not a code/test FAIL.

## CIEL semantic consumer

Repository: `AdrianLipa90/Ciel-Semantic-Model-`  
Branch: `feat/relation-event-hypergraph-bridge-v0.1`  
Candidate pin: `67157523badc1460eefc18f75b75ff20500dcbc3`  
Stacked draft PR: `#27`, base `feat/operator-signature-bridge-v0.1`, mergeable.

Independent structural GIVES harness: PASS for valid full graph plus missing-port, UniversalRole tamper, relation-family tamper, forged-signature and raw-commitment adversarial cases.

Hosted workflow run `33299490269` was retried. All matrix jobs again terminated before any workflow step (`steps=null`), so the result is recorded as infrastructure failure rather than code failure.

## Admission status

Exploratory B0–B4 runs may use these exact candidate pins. GREMLIN now has an executed hosted test gate and a 60-task native receipt artifact. `REPORTABLE_V0_1` still requires an executed full suite for both private CIEL components or an equivalent independently reproducible full-suite execution.
