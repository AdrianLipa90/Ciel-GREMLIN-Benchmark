# B0–B4 Adapter Contract v0.1

The benchmark separates **model invocation** from **scoring**. Every live system must emit the same `Prediction` schema and must be captured before scoring.

## Frozen comparison surface

A valid B0–B4 comparison uses the same:

- dataset bytes (`dataset_sha256`),
- benchmark commit,
- model provider and model ID,
- model parameters (temperature/top-p/seed where supported),
- replicate index,
- tool surface and world state.

System-specific prompts may differ because B1–B4 expose different control layers; each prompt is independently committed with `prompt_sha256`.

## System contracts

| ID | Research | Typed semantic control | Execution gate | Required receipts |
|---|---:|---:|---:|---|
| B0 | no | no | no | none |
| B1 | no | no | no | `structured_output` |
| B2 | GREMLIN | no | no | `structured_output`, `gremlin` |
| B3 | no | CIEL | yes | `structured_output`, `ciel`, `execution_gate` |
| B4 | GREMLIN | CIEL | yes | all four |

`RunManifest.component_commits` pins code provenance. B2/B4 require `gremlin`; B3/B4 require `cielingo` and `ciel_semantic`.

## GREMLIN receipt

The adapter should preserve the native GREMLIN research receipt as a nested value rather than translating it into executable authority. Relevant fields include evidence/research commitments, specialist candidates, source identifiers, contradiction audit, and the native authority booleans.

## CIEL receipt

The CIEL adapter should preserve the typed semantic chain, including where available:

- CasePortFrame,
- OperatorSignature ID + commitment,
- MeaningRoleMultimap commitment,
- RelationHypergraph commitment,
- semantic validation status,
- final execution-gate decision.

## Capture rule

Raw model/system output is evidence. Scoring must replay captured predictions; the scorer must not silently repair malformed outputs.
