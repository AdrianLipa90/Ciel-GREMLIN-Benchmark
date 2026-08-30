# OpenAI Responses Live Adapter

Status: experimental live-capture adapter for benchmark v0.1.

The adapter uses the OpenAI Responses API. B1-B4 force one strict function call named `submit_benchmark_decision`; B0 intentionally does not use schema enforcement. The Responses API supports custom function tools and forced tool selection, and structured tool definitions can be strict.

## Experimental separation

- B0: direct model output, parsed as one JSON object; no function schema.
- B1: strict decision function.
- B2: B1 plus a precomputed GREMLIN research receipt injected into model input.
- B3: same model-facing prompt as B1; precomputed CIEL receipt is provenance-only and the execution-gate receipt is applied after the model decision.
- B4: same model-facing prompt as B2; GREMLIN is injected before the model and CIEL gates after the model.

This preserves the intended ablation: GREMLIN changes available evidence; CIEL changes execution admission.

## Capture command

`ciel-gremlin-benchmark capture-openai` requires a dataset, system id, model id, frozen prompt path, and output JSONL. B2-B4 additionally require a receipt bundle JSONL containing the receipts required by their system contract.

The command reads the API credential from an environment variable (default `OPENAI_API_KEY`). Credentials are never serialized into requests, manifests, predictions, receipts, or repository files.

No API request is made by the test suite. Tests use an in-memory fake Responses transport.

## Receipt bundle row

```json
{
  "task_id": "F6-0042",
  "gremlin": {"...": "native GREMLIN receipt"},
  "ciel": {"...": "native CIEL validation receipt"},
  "execution_gate": {"action": "ALLOW", "...": "gate provenance"}
}
```

`execution_gate.action` is fail-closed and must be one of `ALLOW`, `ASK`, `REJECT`, or `DEFER`. `ASK`, `REJECT`, and `DEFER` override any model request to execute and clear its tool arguments.

## Result status

Live captures produced before exact pinned component full-suite validation remain `EXPLORATORY`; they are not `REPORTABLE_V0_1`.
