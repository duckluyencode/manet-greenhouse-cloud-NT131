"""
Sinh contracts/parity_cases.json: bộ test vector chung cho bản Python (chuẩn)
và bản C++ (simulation/caar-logic/caar_logic.h).

Gồm 3 phần:
- heuristic_cases: danh sách robot -> luật và trọng số kỳ vọng (tính bằng
  cloud-service/app/heuristic.py). Các ca biên của bảng 14.2 có kỳ vọng viết
  tay; script dừng nếu bản Python không khớp kỳ vọng đó.
- cost_cases: chi phí c_i của một node (mục 4.1).
- gateway_cases: chuỗi sự kiện gọi Cloud -> mức hạ cấp và log (mục 7.3).
  Kỳ vọng viết tay theo đặc tả vì cloud không chạy máy trạng thái này.

Chạy: python scripts/gen_parity_cases.py
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud-service"))

from app.heuristic import (  # noqa: E402
    WEIGHT_TABLE,
    NodeSample,
    choose_weights,
    node_cost,
)

DEFAULT_OUT = ROOT / "contracts" / "parity_cases.json"
BALANCED = {"hop_weight": 0.4, "rssi_weight": 0.3, "energy_weight": 0.3}


def nodes(*pairs: tuple[float, float]) -> list[dict]:
    return [{"rssi_avg": r, "energy_remaining_pct": e} for r, e in pairs]


# Ca biên có kỳ vọng viết tay (bảng 14.2 và quy ước mục 7.2).
HAND_CASES: list[tuple[str, list[dict], str]] = [
    ("f_low_threshold_3_of_10", nodes(*[(-60, 10)] * 3, *[(-60, 80)] * 7), "low_battery"),
    ("f_low_below_threshold_2_of_10", nodes(*[(-60, 10)] * 2, *[(-60, 80)] * 8), "balanced"),
    ("energy_exactly_20_not_weak", nodes(*[(-60, 20)] * 3, *[(-60, 80)] * 7), "balanced"),
    ("energy_19_99_is_weak", nodes(*[(-60, 19.99)] * 3, *[(-60, 80)] * 7), "low_battery"),
    ("rule_order_battery_wins", nodes(*[(-85, 10)] * 2, *[(-85, 90)] * 2), "low_battery"),
    ("even_median_poor_signal", nodes((-85, 90), (-80, 90), (-75, 90), (-60, 90)), "poor_signal"),
    ("rssi_clamp_low", nodes((-100, 90), (-60, 90)), "balanced"),
    ("rssi_clamp_both_ends", nodes((-120, 90), (0, 90), (-120, 90)), "poor_signal"),
    ("median_exactly_minus_75", nodes((-75, 90)), "balanced"),
    ("median_minus_75_5", nodes((-75.5, 90)), "poor_signal"),
    ("even_median_exactly_minus_75", nodes((-80, 90), (-70, 90)), "balanced"),
    ("single_weak_node", nodes((-50, 5)), "low_battery"),
    ("normal_network", nodes(*[(-55, 95)] * 5), "balanced"),
    ("f_low_1_of_3", nodes((-60, 10), (-60, 90), (-60, 90)), "low_battery"),
    ("f_low_1_of_4", nodes((-60, 10), (-60, 90), (-60, 90), (-60, 90)), "balanced"),
]

COST_WEIGHTS = [
    (1.0, 0.0, 0.0),
    (0.4, 0.3, 0.3),
    (0.2, 0.3, 0.5),
    (0.3, 0.5, 0.2),
]
COST_POINTS = [
    (-40, 1.0),
    (-90, 0.0),
    (-65, 0.5),
    (-120, 0.2),
    (-30, 1.0),
    (-72.5, 0.83),
]

# Mỗi bước: thời điểm gọi Cloud (s) và kết quả. "invalid" = Cloud trả trọng số
# sai (tổng khác 1), Gateway coi như lỗi.
GATEWAY_CASES = [
    {
        "name": "doc_example_ttl_300",
        "description": "Mục 7.3: cập nhật cuối ở 295 s, mất cloud 300-600 s, TTL 300 s",
        "ttl_s": 300,
        "steps": (
            [{"t": 290, "result": "ok", "weights": "low_battery"}]
            + [{"t": 295, "result": "ok", "weights": "poor_signal"}]
            + [{"t": t, "result": "timeout"} for t in range(300, 600, 5)]
            + [{"t": 600, "result": "ok", "weights": "low_battery"}]
        ),
    },
    {
        "name": "short_outage_keeps_cache",
        "description": "Mất cloud ngắn hơn TTL: dùng trọng số cache, không stale",
        "ttl_s": 60,
        "steps": (
            [{"t": 0, "result": "ok", "weights": "low_battery"}]
            + [{"t": t, "result": "timeout"} for t in range(5, 30, 5)]
            + [{"t": 30, "result": "ok", "weights": "balanced"}]
        ),
    },
    {
        "name": "ttl_15_goes_stale",
        "description": "TTL 15 s: tuổi cache đúng bằng TTL là hết hạn (>=)",
        "ttl_s": 15,
        "steps": (
            [{"t": 0, "result": "ok", "weights": "poor_signal"}]
            + [{"t": t, "result": "timeout"} for t in range(5, 25, 5)]
        ),
    },
    {
        "name": "no_cache_before_first_reply",
        "description": "Chưa từng nhận trọng số: lỗi đầu tiên vào thẳng mức 3",
        "ttl_s": 60,
        "steps": [
            {"t": 0, "result": "timeout"},
            {"t": 5, "result": "timeout"},
            {"t": 10, "result": "ok", "weights": "low_battery"},
        ],
    },
    {
        "name": "invalid_weights_count_as_failure",
        "description": "Trọng số sai miền bị Gateway từ chối như timeout",
        "ttl_s": 60,
        "steps": [
            {"t": 0, "result": "ok", "weights": "low_battery"},
            {"t": 5, "result": "invalid"},
            {"t": 10, "result": "ok", "weights": "balanced"},
        ],
    },
]


def weights_dict(rule: str) -> dict:
    wh, wr, we = WEIGHT_TABLE[rule]
    return {"hop_weight": wh, "rssi_weight": wr, "energy_weight": we}


def expected_heuristic(node_list: list[dict]) -> dict:
    d = choose_weights(NodeSample(n["rssi_avg"], n["energy_remaining_pct"]) for n in node_list)
    return {
        "rule": d.rule,
        "hop_weight": d.hop_weight,
        "rssi_weight": d.rssi_weight,
        "energy_weight": d.energy_weight,
    }


def random_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for i in range(count):
        n = rng.randint(1, 20)
        # Một nửa dùng RSSI nguyên (đúng như telemetry thật), một nửa số thực.
        integer = i % 2 == 0
        node_list = []
        for _ in range(n):
            rssi = rng.randint(-120, 0) if integer else round(rng.uniform(-120, 0), 2)
            # Thiên về vùng quanh ngưỡng 20% để hay chạm biên.
            energy = rng.choice([rng.randint(0, 100), rng.choice([19, 20, 21])])
            node_list.append({"rssi_avg": rssi, "energy_remaining_pct": energy})
        cases.append(
            {
                "name": f"random_{i:03d}",
                "nodes": node_list,
                "expected": expected_heuristic(node_list),
            }
        )
    return cases


def gateway_expected(case: dict) -> dict:
    """Kỳ vọng của máy trạng thái 3 mức, viết theo mục 7.3.

    Ghi chú: đây là đặc tả bằng Python để sinh kỳ vọng; bản chạy thật là C++.
    """
    ttl = case["ttl_s"]
    level = 1
    cache = None
    last_success = None
    out_steps = []
    for step in case["steps"]:
        t = step["t"]
        events = []
        if step["result"] == "ok":
            if level != 1:
                events.append("outage_end")
            events.append("param_update")
            level = 1
            cache = weights_dict(step["weights"])
            last_success = t
        else:
            if level == 1:
                events.append("outage_start")
                level = 2
            age = float("inf") if last_success is None else t - last_success
            if level == 2 and age >= ttl:
                events.append("stale_detected")
                level = 3
        active = cache if (level in (1, 2) and cache is not None) else BALANCED
        out_steps.append(
            {**step, "expected_level": level, "expected_events": events, "expected_weights": active}
        )
    return {k: v for k, v in case.items() if k != "steps"} | {"steps": out_steps}


def build(random_count: int, seed: int) -> dict:
    heuristic_cases = []
    for name, node_list, rule in HAND_CASES:
        expected = expected_heuristic(node_list)
        if expected["rule"] != rule:
            raise SystemExit(f"{name}: Python gives {expected['rule']}, spec says {rule}")
        heuristic_cases.append({"name": name, "nodes": node_list, "expected": expected})
    heuristic_cases += random_cases(random_count, seed)

    cost_cases = []
    for wh, wr, we in COST_WEIGHTS:
        for rssi, e in COST_POINTS:
            cost_cases.append(
                {
                    "name": f"cost_w{wh}_{wr}_{we}_rssi{rssi}_e{e}",
                    "weights": {"hop_weight": wh, "rssi_weight": wr, "energy_weight": we},
                    "rssi_avg": rssi,
                    "energy_frac": e,
                    "expected_cost": node_cost(wh, wr, we, rssi, e),
                }
            )

    return {
        "version": 1,
        "generated_by": "scripts/gen_parity_cases.py",
        "weight_table": {rule: weights_dict(rule) for rule in WEIGHT_TABLE},
        "heuristic_cases": heuristic_cases,
        "cost_cases": cost_cases,
        "gateway_cases": [gateway_expected(c) for c in GATEWAY_CASES],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--random", type=int, default=200, help="số ca ngẫu nhiên")
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()

    data = build(args.random, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {args.out}: {len(data['heuristic_cases'])} heuristic, "
        f"{len(data['cost_cases'])} cost, {len(data['gateway_cases'])} gateway cases"
    )


if __name__ == "__main__":
    main()
