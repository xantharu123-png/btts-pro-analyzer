from ev_checker_tab import _signal_inputs
from ev_signal_sources import ModelSignal


def test_signal_inputs_quantize_probability_and_haircut_conservatively():
    signal = ModelSignal(
        key="esports-test",
        label="Test",
        probability=0.8744,
        probability_haircut=0.1786,
        evidence_stage="SHADOW",
        policy_version="test",
        detail="Test",
    )

    probability, haircut, minimum_odds = _signal_inputs(signal)

    assert probability == 87.4
    assert haircut == 17.9
    assert minimum_odds == 1.49
