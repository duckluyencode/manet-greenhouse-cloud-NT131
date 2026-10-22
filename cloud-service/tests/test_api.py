"""Test API theo bảng 14.2 của tài liệu đồ án."""
import time

import pytest
from app.main import app
from fastapi.testclient import TestClient

from .conftest import TEST_API_KEY

AUTH = {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def client():
    # Dùng context manager để lifespan chạy init_db() trên DB tạm của test.
    with TestClient(app) as c:
        yield c


def node(i: int, rssi: float = -60, energy: float = 90, hop: int = 1) -> dict:
    return {
        "node_id": f"r{i}",
        "rssi_avg": rssi,
        "energy_remaining_pct": energy,
        "hop_count": hop,
    }


def snapshot(nodes: list[dict], **overrides) -> dict:
    body = {"run_id": 1, "timestamp": time.time(), "nodes": nodes}
    body.update(overrides)
    return body


def optimize(client: TestClient, body: dict, headers: dict | None = None):
    return client.post("/optimize", json=body, headers=AUTH if headers is None else headers)


def assert_weights_valid(weights: dict) -> None:
    values = [weights["hop_weight"], weights["rssi_weight"], weights["energy_weight"]]
    assert all(v >= 0 for v in values)
    assert abs(sum(values) - 1.0) <= 0.001


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_snapshot(client) -> None:
    body = snapshot(
        [
            {"node_id": "r1", "rssi_avg": -72, "energy_remaining_pct": 45, "hop_count": 2},
            {"node_id": "r2", "rssi_avg": -85, "energy_remaining_pct": 12, "hop_count": 3},
        ]
    )
    response = optimize(client, body)
    assert response.status_code == 200
    data = response.json()
    assert data["rule"] in {"low_battery", "poor_signal", "balanced"}
    assert_weights_valid(data["weights"])


@pytest.mark.parametrize(
    "bad_node",
    [
        node(1, energy=150),  # pin ngoài miền
        node(1, energy=-1),
        node(1, hop=0),  # hop không hợp lệ
        node(1, rssi=-121),
        node(1, rssi=5),
        {"node_id": 1, "rssi_avg": -60, "energy_remaining_pct": 90, "hop_count": 1},
    ],
    ids=["energy_150", "energy_neg", "hop_0", "rssi_low", "rssi_pos", "node_id_int"],
)
def test_invalid_node_rejected(client, bad_node) -> None:
    assert optimize(client, snapshot([bad_node])).status_code == 422


def test_empty_nodes_rejected(client) -> None:
    assert optimize(client, snapshot([])).status_code == 422


@pytest.mark.parametrize(
    ("nodes", "rule", "expected"),
    [
        # Ngưỡng f_low: 10 robot, 3 robot pin < 20% -> đúng ngưỡng, dùng >=.
        (
            [node(i, energy=10) for i in range(3)] + [node(i, energy=80) for i in range(3, 10)],
            "low_battery",
            (0.2, 0.3, 0.5),
        ),
        # Pin đúng 20% không tính là yếu.
        (
            [node(i, energy=20) for i in range(3)] + [node(i, energy=80) for i in range(3, 10)],
            "balanced",
            (0.4, 0.3, 0.3),
        ),
        # Thứ tự luật: cả hai luật đúng, luật pin thắng.
        (
            [node(i, rssi=-85, energy=10) for i in range(2)]
            + [node(i, rssi=-85, energy=90) for i in range(2, 4)],
            "low_battery",
            (0.2, 0.3, 0.5),
        ),
        # Trung vị chẵn: -77.5 dBm < -75 -> poor_signal.
        (
            [node(i, rssi=r, energy=90) for i, r in enumerate([-85, -80, -75, -60])],
            "poor_signal",
            (0.3, 0.5, 0.2),
        ),
        # Kẹp RSSI: -100 -> -90; trung vị -75, không nhỏ hơn ngưỡng.
        (
            [node(1, rssi=-100, energy=90), node(2, rssi=-60, energy=90)],
            "balanced",
            (0.4, 0.3, 0.3),
        ),
        # Bình thường.
        ([node(i, rssi=-55, energy=95) for i in range(5)], "balanced", (0.4, 0.3, 0.3)),
    ],
    ids=["f_low_threshold", "energy_exactly_20", "rule_order", "even_median", "rssi_clamp", "normal"],
)
def test_heuristic_rules(client, nodes, rule, expected) -> None:
    response = optimize(client, snapshot(nodes))
    assert response.status_code == 200
    data = response.json()
    assert data["rule"] == rule
    weights = data["weights"]
    assert (weights["hop_weight"], weights["rssi_weight"], weights["energy_weight"]) == expected
    assert_weights_valid(weights)


def test_missing_api_key(client) -> None:
    assert optimize(client, snapshot([node(1)]), headers={}).status_code == 401


def test_wrong_api_key(client) -> None:
    response = optimize(client, snapshot([node(1)]), headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_unconfigured_api_key_fails_closed(client, monkeypatch) -> None:
    monkeypatch.delenv("CAAR_API_KEY")
    assert optimize(client, snapshot([node(1)])).status_code == 503


@pytest.mark.parametrize("skew", [-31, 31])
def test_stale_or_future_timestamp(client, skew) -> None:
    body = snapshot([node(1)], timestamp=time.time() + skew)
    assert optimize(client, body).status_code == 400


def test_nonce_replay_rejected(client) -> None:
    body = snapshot([node(1)], nonce="nonce-replay-test")
    assert optimize(client, body).status_code == 200
    assert optimize(client, body).status_code == 400


def test_nonce_is_optional(client) -> None:
    body = snapshot([node(1)])
    assert optimize(client, body).status_code == 200
    assert optimize(client, body).status_code == 200


def test_metrics_summary(client) -> None:
    from app import db

    for seed, pdr in [(1, 0.9), (2, 0.8)]:
        run_id = db.save_run("no_cloud", "baseline", seed, 10, 0.2, {"dmax_ms": 20})
        db.save_metrics(run_id, pdr=pdr, avg_delay_ms=10.0)

    response = client.get("/metrics/summary", headers=AUTH)
    assert response.status_code == 200
    [row] = response.json()
    assert row["config_type"] == "no_cloud"
    assert row["runs"] == 2
    assert row["pdr_mean"] == pytest.approx(0.85)


def test_metrics_summary_requires_key(client) -> None:
    assert client.get("/metrics/summary").status_code == 401


def test_optimize_logs_param_update(client) -> None:
    from app import db

    assert optimize(client, snapshot([node(1)], run_id=42)).status_code == 200
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT event_type FROM cloud_events WHERE run_id = 42"
        ).fetchall()
    assert rows == [("param_update",)]
