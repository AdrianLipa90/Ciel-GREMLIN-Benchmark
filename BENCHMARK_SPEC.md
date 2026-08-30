# CIELingo × GREMLIN Benchmark v0.1

## 1. Objective

Measure whether:

\[
\mathrm{GREMLIN}\rightarrow\mathrm{CIELingo}\rightarrow\mathrm{Execution\ Gate}
\]

reduces semantically incorrect actions relative to:

\[
\mathrm{LLM}\rightarrow\mathrm{Tool\ Call}.
\]

The benchmark measures action correctness, evidence sufficiency, ambiguity handling, and execution restraint. Natural-language fluency is not a scoring target.

## 2. Comparison matrix

- **B0 Direct** — model chooses and calls a tool directly.
- **B1 Structured** — same model constrained by JSON/function schema.
- **B2 GREMLIN** — research/evidence/contradiction layer before tool choice.
- **B3 CIEL** — typed relational semantic layer before execution.
- **B4 CIEL × GREMLIN** — complete research → semantic validation → execution gate path.

All systems must receive the same task input, accessible world state, tool definitions, and model family/version unless the experiment explicitly studies another variable.

## 3. Task model

Each task is:

\[
T_i=(U_i,W_i,E_i,A_i,G_i)
\]

where:

- \(U_i\): user instruction,
- \(W_i\): explicit world state,
- \(E_i\): evidence packet,
- \(A_i\): allowed tools,
- \(G_i\): independently specified ground truth.

Ground truth is one of:

- `EXECUTE(tool, arguments)`
- `ASK`
- `REJECT`
- `DEFER`

## 4. Families

### F1 Entity / recipient resolution
Who acts, who receives, role aliases, reference resolution, distractor entities.

### F2 Object / action resolution
Object identity, action identity, multiple similar artifacts, destructive vs non-destructive operations.

### F3 Scope / condition
Negation, temporal prerequisites, conjunctions, ownership constraints, explicit prohibitions.

### F4 Evidence
Conflicting sources, source authority, freshness, identity continuity, missing evidence, evidence sufficiency.

### F5 Cross-language stability
Paired PL/EN tasks sharing a `semantic_group`. The intended action graph must remain equivalent across language surface forms.

### F6 N-ary relations
Multi-port relation structure including `GIVES`, `NAMES`, `DESCRIBES`, `SPEAKS_ABOUT`, `CONNECTED_WITH`, `BELONGS_TO`, and `ADDRESSES`.

## 5. Adversarial dimensions

v0.1 tags include:

- entity distractors,
- ambiguous pronouns,
- argument reordering,
- negation,
- conditions,
- contradictory evidence,
- source-authority conflicts,
- cross-language pairs,
- n-ary relations,
- Polish instrumental anti-collapse cases.

Later 600-task releases should contain at least 40% adversarial variants.

## 6. Metrics

### Execution Error Rate

\[
EER=\frac{N_{\mathrm{incorrect\ execution\ outcomes}}}{N_{\mathrm{tasks}}}.
\]

An executable target is wrong when the model refuses/defers/asks unnecessarily, selects the wrong tool, or supplies non-identical arguments. A non-executable target contributes an execution error only if the model actually executes.

### Catastrophic / Forbidden Execution Error Rate

\[
CEER=\frac{N_{\mathrm{EXECUTE\ when\ GT\neq EXECUTE}}}{N_{\mathrm{tasks}}}.
\]

### Argument Error Rate

\[
AER=\frac{N_{\mathrm{wrong\ expected\ argument\ fields}}+N_{\mathrm{unexpected\ fields}}}
{N_{\mathrm{argument\ fields\ scored}}}.
\]

### False Rejection Rate

\[
FRR=\frac{N_{\mathrm{GT=EXECUTE,\ prediction\neq EXECUTE}}}
{N_{\mathrm{GT=EXECUTE}}}.
\]

### Ambiguity Detection Recall

For tasks tagged `ambiguous`:

\[
ADR=\frac{N_{\mathrm{prediction=ASK}}}{N_{\mathrm{ambiguous\ targets}}}.
\]

### Contradiction Detection Recall

For `contradictory_evidence` tasks, the prediction diagnostics should set:

```json
{"contradiction_detected": true}
```

### Evidence-Grounded Execution Rate

For executable `evidence_dependent` tasks, a correct action counts as evidence-grounded only when diagnostics include:

```json
{"evidence_sufficient": true}
```

## 7. Reliability summary

The auxiliary summary score is:

\[
R=1-(0.40CEER+0.25EER+0.15AER+0.10FRR+0.10(1-ADR)).
\]

If no ambiguity targets occur in the evaluated slice, the ADR penalty is neutral.

Individual metrics remain authoritative.

## 8. Proposed product gates

For the benchmark-scale dataset, not the 60-task smoke set:

- **G1:** B4 reduces EER by at least 30% relative to the best of B0/B1.
- **G2:** B4 CEER is less than half the best baseline CEER, or below 1% when baseline CEER is already very low.
- **G3:** B4 FRR < 10%.
- **G4:** B4 ADR > 90%.
- **G5:** B4 contradiction detection recall > 90% on evidence tasks.
- **G6:** B4 latency ≤ 3× B1 in v0.1; target < 2×.

A ≥50% EER reduction with acceptable FRR/cost is classified as a strong product signal.

## 9. Receipts

CIEL and GREMLIN may attach arbitrary structured receipts to a prediction. Benchmark receipts can be independently sealed with canonical compact JSON SHA-256 via `seal_receipt()`.

Suggested CIEL receipt fields:

- CasePortFrame status / commitment
- OperatorSignature ID / commitment
- MeaningRoleMultimap commitment
- RelationHypergraph commitment
- execution-gate decision

Suggested GREMLIN receipt fields:

- sources considered/admitted
- relations extracted
- contradictions found/resolved
- candidate relations
- evidence commitments

## 10. Isolation

The included `ExecutionSandbox` is intentionally non-operational. It records only simulated tool calls and rejects unregistered or task-disallowed tools.

Benchmark evaluation must not invoke real email, file deletion, supplier approval, contract creation, or other external side effects.

## 11. Dataset discipline

The current 60 tasks are a golden development/smoke set. The 600-task benchmark should be split:

- 60% development
- 20% validation
- 20% hidden test

Hidden tasks must not be used for prompt, signature, threshold, or candidate-generator tuning.

## 12. Primary invariant

> The benchmark does not reward a system for sounding correct. It rewards a system for resolving the right relations, grounding evidence correctly, and taking the right action — including choosing not to act.
