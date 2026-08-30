from ciel_gremlin_benchmark.schema import Decision, Prediction
from ciel_gremlin_benchmark.systems import get_system_contract, validate_prediction_contract


def test_b4_requires_both_research_and_semantic_receipts():
    contract = get_system_contract("B4")
    assert contract.gremlin is True
    assert contract.ciel is True
    assert contract.execution_gate is True
    prediction = Prediction(system_id="B4", task_id="T", decision=Decision.DEFER)
    issues = validate_prediction_contract(prediction)
    assert any("gremlin" in issue for issue in issues)
    assert any("ciel" in issue for issue in issues)
    assert any("execution_gate" in issue for issue in issues)


def test_b0_has_no_required_receipts():
    prediction = Prediction(system_id="B0", task_id="T", decision=Decision.DEFER)
    assert validate_prediction_contract(prediction) == []
