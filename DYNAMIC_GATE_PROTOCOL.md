# Dynamic CIEL Execution Gate Protocol v0.1

Status: benchmark candidate protocol for proposal-bound semantic gating.

## Purpose

B3/B4 must measure a semantic firewall that evaluates the model's **actual proposed action**, not a task-level action selected before the model runs.

The reportable path is therefore:

```text
user/task input
-> CIEL semantic receipt (pre-model, hidden from model)
-> model proposal: decision + tool + arguments
-> proposal SHA-256
-> dynamic CIEL execution gate
-> ALLOW / ASK / REJECT / DEFER
```

GREMLIN remains pre-model evidence context in B2/B4. CIEL remains post-model control in B3/B4.

## Leakage firewall

A dynamic run rejects any input receipt bundle that already contains an `execution_gate` action. The gate action must be created only after the model proposal exists.

The gate does not receive benchmark ground truth. Tests explicitly mutate ground truth while holding the task surface, semantic receipt and proposal fixed and require an identical gate result.

## CIEL execution contract

A CIEL receipt used by the dynamic gate carries:

```json
{
  "candidate_only": true,
  "source_commitment": "<sha256 from the CIEL semantic source receipt>",
  "execution_contract": {
    "schema": "CIEL_EXECUTION_CONTRACT_V0_1",
    "status": "READY",
    "tool": "transfer_object",
    "required_arguments": ["sender", "recipient", "object"],
    "argument_bindings": {
      "sender": "USER",
      "recipient": "Zosia",
      "object": "book"
    },
    "allow_extra_arguments": false
  },
  "execution_contract_sha256": "<sha256>"
}
```

The projection must be generated from CIEL semantic analysis and world-state bindings without access to benchmark ground truth.

Admitted semantic statuses are:

- `READY`
- `AMBIGUOUS`
- `MISSING_ARGUMENT`
- `MISSING_EVIDENCE`
- `CONTRADICTORY`
- `POLICY_REJECT`

For an `EXECUTE` proposal, non-ready statuses deterministically block as:

```text
AMBIGUOUS        -> ASK
MISSING_ARGUMENT -> ASK
MISSING_EVIDENCE -> DEFER
CONTRADICTORY    -> DEFER
POLICY_REJECT    -> REJECT
```

For `READY`, the proposed tool and argument bindings must match the semantic execution contract. Missing required arguments produce `ASK`; wrong tool/binding or unexpected arguments produce `REJECT`.

The gate never repairs incorrect arguments and never promotes `ASK`, `REJECT` or `DEFER` into `EXECUTE`.

## Dynamic gate receipt

Every gated proposal emits `CIEL_DYNAMIC_EXECUTION_GATE_V0_1` containing:

- gate action;
- reason code(s);
- SHA-256 of the exact pre-gate proposal;
- CIEL source commitment;
- execution-contract commitment;
- `ground_truth_used=false`.

The proposal hash is checked again by the adapter before the action is applied.

## Legacy path

The earlier adapter that consumes a precomputed `execution_gate.action` remains available for historical replay only. It is **not eligible for `REPORTABLE_V0_1` live results**.

A reportable B3/B4 live run must use `DynamicOpenAIResponsesAdapter` or a later adapter preserving the same proposal-bound and no-ground-truth invariants.
