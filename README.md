# CIEL × GREMLIN Benchmark

**Version:** 0.1  
**Status:** executable benchmark scaffold + 60 golden tasks  
**Purpose:** measure whether `GREMLIN → CIELingo → execution gate` reduces semantically incorrect AI-agent actions compared with direct and structured tool-calling baselines.

The benchmark evaluates execution reliability rather than prose quality.

## Systems

| ID | System |
|---|---|
| B0 | Direct LLM agent |
| B1 | LLM + structured/function schema |
| B2 | LLM + GREMLIN research/audit |
| B3 | LLM + CIEL semantic control |
| B4 | LLM + GREMLIN + CIEL |

The same base model, tool surface, task set, and execution sandbox must be used across systems.

## v0.1 dataset

`dataset/golden_v0_1.jsonl` contains 60 hand-specified tasks:

- F1 — entity / recipient resolution
- F2 — object / action resolution
- F3 — negation, scope, and conditions
- F4 — evidence-conditional execution
- F5 — cross-language semantic stability
- F6 — n-ary relations

Each family currently contains 10 tasks. This is the golden smoke set; the planned benchmark-scale dataset is 600 tasks.

## Core decisions

Every task has exactly one ground-truth decision:

- `EXECUTE(tool, arguments)`
- `ASK`
- `REJECT`
- `DEFER`

The system is not rewarded for always executing, and it is not rewarded for refusing everything.

## Primary metrics

- Execution Error Rate (EER)
- Catastrophic / Forbidden Execution Error Rate (CEER)
- Argument Error Rate (AER)
- False Rejection Rate (FRR)
- Ambiguity Detection Recall (ADR)
- Contradiction Detection Recall (CDR)
- Evidence-Grounded Execution Rate (EGER)
- composite reliability score

The benchmark always reports the individual metrics; the composite score is only a summary statistic.

## Quick start

```bash
python -m pip install -e ".[dev]"
ciel-gremlin-benchmark validate dataset/golden_v0_1.jsonl
pytest
```

To score a captured system run:

```bash
ciel-gremlin-benchmark score \
  dataset/golden_v0_1.jsonl \
  predictions/b4.jsonl \
  --system-id B4 \
  --output results/b4.json \
  --include-records
```

A prediction line must contain at least:

```json
{
  "system_id": "B4",
  "task_id": "F6-001",
  "decision": "EXECUTE",
  "tool": "transfer_object",
  "arguments": {
    "sender": "USER",
    "recipient": "Zosia",
    "object": "book"
  }
}
```

## Safety and isolation

The benchmark sandbox never calls external tools. `ExecutionSandbox` records simulated calls and rejects tools not explicitly allowed by the task.

## CIEL × GREMLIN contract

GREMLIN is treated as a candidate/evidence/relation discovery and adversarial-audit layer. Candidate output does not automatically become executable authority.

CIEL is evaluated as the typed semantic control layer that can bind operator-specific roles, validate relation structure, preserve provenance/receipts, and gate execution.

The benchmark is designed so that each layer can also be ablated independently.

See [`BENCHMARK_SPEC.md`](BENCHMARK_SPEC.md) for protocol details.
