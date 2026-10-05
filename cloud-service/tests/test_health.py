import time

from fastapi.testclient import TestClient

from app.main import app

# Test client gọi endpoint trực tiếp mà không cần khởi chạy server riêng.
client = TestClient(app)


# Payload chung chứa timestamp hiện tại và nonce riêng cho mỗi request.
def telemetry_payload(nonce: str) -> dict[str, str | float | int]:
    return {
        "node_id": "node-1",
        "rssi_avg": -65.0,
        "energy_remaining_pct": 80.0,
        "hop_count": 3,
        "timestamp": time.time(),
        "nonce": nonce,
    }


def test_health() -> None:
    """Kiểm tra endpoint health báo service đang hoạt động."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_returns_weights() -> None:
    """Kiểm tra optimize nhận telemetry hợp lệ và trả trọng số."""
    response = client.post(
        "/optimize", json=telemetry_payload("test-optimize")
    )
    assert response.status_code == 200
    body = response.json()
    assert "weights" in body
    assert body["twin_rejected"] is False


def test_detect_stub() -> None:
    """Kiểm tra endpoint detect trả kết quả placeholder."""
    response = client.post("/detect", json=telemetry_payload("test-detect"))
    assert response.status_code == 200
    assert response.json()["anomaly"] is False
