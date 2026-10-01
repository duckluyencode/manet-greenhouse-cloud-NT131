from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_returns_weights() -> None:
    payload = {
        "node_id": "node-1",
        "rssi_avg": -65.0,
        "energy_remaining_pct": 80.0,
        "hop_count": 3,
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "weights" in body
    assert body["twin_rejected"] is False


def test_detect_stub() -> None:
    payload = {
        "node_id": "node-1",
        "rssi_avg": -65.0,
        "energy_remaining_pct": 80.0,
        "hop_count": 3,
    }
    response = client.post("/detect", json=payload)
    assert response.status_code == 200
    assert response.json()["anomaly"] is False
