"""Test hàm thuần heuristic và parity với contracts/parity_cases.json."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.heuristic import (
    NodeSample,
    choose_weights,
    node_cost,
    select_rule,
    twice_median,
)
from app.models import Weights

PARITY_FILE = Path(__file__).resolve().parents[2] / "contracts" / "parity_cases.json"


def test_twice_median_odd_and_even() -> None:
    assert twice_median([-60, -80, -70]) == -140
    assert twice_median([-85, -80, -75, -60]) == -155


def test_empty_network_is_balanced() -> None:
    assert select_rule([]) == "balanced"


def test_poor_signal_boundary_is_strict() -> None:
    # Trung vị đúng -75 dBm (r = 0.3) không phải poor_signal.
    assert select_rule([NodeSample(-75, 90)]) == "balanced"
    assert select_rule([NodeSample(-75.5, 90)]) == "poor_signal"


@pytest.mark.parametrize(
    ("weights", "rssi", "energy", "expected"),
    [
        ((1.0, 0.0, 0.0), -90, 0.0, 1.0),  # w_h = 1: mọi node như nhau (AODV gốc)
        ((0.4, 0.3, 0.3), -40, 1.0, 0.4),  # link tốt nhất, pin đầy
        ((0.4, 0.3, 0.3), -90, 0.0, 1.0),  # link tệ nhất, hết pin
        ((0.4, 0.3, 0.3), -120, 0.5, 0.85),  # RSSI dưới -90 kẹp về r = 0
    ],
)
def test_node_cost(weights, rssi, energy, expected) -> None:
    assert node_cost(*weights, rssi, energy) == pytest.approx(expected)


def test_weights_sum_validation() -> None:
    Weights(hop_weight=0.4, rssi_weight=0.3, energy_weight=0.3)
    Weights(hop_weight=0.4, rssi_weight=0.3, energy_weight=0.3009)
    with pytest.raises(ValidationError):
        Weights(hop_weight=0.5, rssi_weight=0.3, energy_weight=0.3)
    with pytest.raises(ValidationError):
        Weights(hop_weight=1.2, rssi_weight=-0.2, energy_weight=0.0)


def test_parity_cases_match_reference() -> None:
    """Bộ test vector phải khớp với bản Python (bản chuẩn)."""
    cases = json.loads(PARITY_FILE.read_text(encoding="utf-8"))
    assert cases["heuristic_cases"], "parity_cases.json has no heuristic cases"
    for case in cases["heuristic_cases"]:
        nodes = [NodeSample(n["rssi_avg"], n["energy_remaining_pct"]) for n in case["nodes"]]
        decision = choose_weights(nodes)
        expected = case["expected"]
        assert decision.rule == expected["rule"], case["name"]
        assert decision.hop_weight == expected["hop_weight"], case["name"]
        assert decision.rssi_weight == expected["rssi_weight"], case["name"]
        assert decision.energy_weight == expected["energy_weight"], case["name"]

    for case in cases["cost_cases"]:
        w = case["weights"]
        cost = node_cost(
            w["hop_weight"], w["rssi_weight"], w["energy_weight"],
            case["rssi_avg"], case["energy_frac"],
        )
        assert cost == pytest.approx(case["expected_cost"], abs=1e-12), case["name"]
