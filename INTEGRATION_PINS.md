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

## CIELingo producer

Repository: `AdrianLipa90/cielingo-canon`  
Branch: `feat/relation-card-identity-transport-v0.1`  
Candidate pin: `7d698b276960d0e8067e30adbdab22cdea964f04`  
Stacked draft PR: `#20`, base `feat/action-operator-coverage-v0.2`, mergeable.

The producer path is now:

```text
RegionalSolveResult.candidates.card_id
→ RelationHypergraph entity token span
→ RelationEntityCardBindings
→ exact relation_hypergraph_commitment
→ SentenceEquation.relation_entity_card_bindings
```

A relation entity receives semantic identity only through exact token-index continuity and exactly one distinct regional `card_id`. `slot_id` is retained only as provenance. The producer receipt partitions every relation entity as bound, ambiguous, unbound, or implicit and binds the receipt commitment to the exact relation-hypergraph commitment.

Validation status on the pinned candidate:
- isolated producer/consumer identity contract harness: **10/10 PASS**
- current full repository suite: **UNTESTED**
- hosted CI on current card-identity head: no executed run recorded at pin time

## CIEL semantic consumer

Repository: `AdrianLipa90/Ciel-Semantic-Model-`  
Branch: `feat/relation-card-identity-bridge-v0.1`  
Candidate pin: `0435ce8ecfd97f09faa0ea702a847d62dd91630a`  
Stacked draft PR: `#29`, base `feat/entity-grounding-by-card-id-v0.1`, mergeable.

The consumer path is:

```text
validated RelationHypergraph
+ validated RelationEntityCardBindings
→ exact equation/language/graph/entity/token continuity
→ source-language atlas corroboration of supplied card_id
→ shared-card world resolution
→ RelationEntityGroundingBundle
→ resolved world-entity cross-index only
```

A supplied singleton `card_id` cannot redirect grounding unless it matches the exact source-language atlas form. Ambiguous or unbound producer identity remains fail-closed. `slot_id` never establishes identity. PL/EN identity may cross the language boundary only through the same corroborated `card_id`.

Validation status on the pinned candidate:
- isolated producer/consumer identity contract harness: **10/10 PASS**
- isolated source-atlas corroboration checks: **3/3 PASS**
- pinned cross-repo golden contract: implemented, current-head execution pending
- current full repository suite: **UNTESTED**

## Benchmark consumer boundary

The benchmark no longer resolves CIEL relation entities with its own surface/alias matcher. B3/B4 READY projection requires a `CIEL_RELATION_ENTITY_GROUNDING_BUNDLE_V0_1` whose equation ID, language ID, relation-hypergraph commitment and card-binding commitment match the exact `SentenceEquation` receipts.

Therefore:

```text
surface coincidence alone
≠ execution authority

slot_id coincidence
≠ execution authority

validated shared card identity + exact receipt continuity
→ candidate execution argument binding
```

This keeps benchmark scoring downstream of the CIEL/Semantic boundary rather than silently recreating a second grounding system inside the harness.

## Admission status

Exploratory B0–B4 runs may use these exact candidate pins once CIEL receipt coverage is regenerated from the pinned card-identity stack. GREMLIN has an executed hosted test gate and a 60-task native receipt artifact. `REPORTABLE_V0_1` still requires an executed full suite for both private CIEL components or an equivalent independently reproducible full-suite execution.
