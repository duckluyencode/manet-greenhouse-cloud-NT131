"""
Cloud Service — bộ tối ưu hóa định tuyến cho kiến trúc CAAR (Cloud-Assisted Adaptive Routing).

Endpoints:
- GET  /health    : kiểm tra service còn sống
- POST /optimize  : nhận telemetry, trả về trọng số định tuyến mới (nhánh a - Must-have)
- POST /detect    : nhận telemetry, trả cảnh báo bất thường (nhánh b - Should-have)

Owner: B (Cloud/Backend Lead)
"""
from fastapi import FastAPI

from app.db import init_db
from app.models import DetectResponse, OptimizeResponse, TelemetrySnapshot

app = FastAPI(title="CAAR Cloud-Service", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(telemetry: TelemetrySnapshot) -> OptimizeResponse:
    """
    Nhánh (a) — tối ưu hiệu năng (Must-have).

    TODO (Week 3-4, Owner B): thay công thức placeholder bằng
    weighted heuristic thật (RSSI + hop-count + năng lượng còn lại).
    """
    candidate_weights = _compute_candidate_weights(telemetry)

    # TODO (Week 6-7, Owner B, Should-have):
    # Bật Digital-Twin validation khi đã huấn luyện model thật.
    # prediction = predict_effect(telemetry, candidate_weights)
    # if prediction.worse_than_current and telemetry.last_known_weights:
    #     return OptimizeResponse(
    #         weights=telemetry.last_known_weights, twin_rejected=True
    #     )

    return OptimizeResponse(weights=candidate_weights, twin_rejected=False)


def _compute_candidate_weights(telemetry: TelemetrySnapshot) -> dict:
    """Placeholder — công thức thật sẽ thêm ở Week 3-4."""
    del telemetry  # chưa dùng tới, sẽ dùng khi cài logic thật
    return {"rssi_weight": 0.5, "energy_weight": 0.3, "hop_weight": 0.2}


@app.post("/detect", response_model=DetectResponse)
def detect(telemetry: TelemetrySnapshot) -> DetectResponse:
    """Nhánh (b) — phát hiện bất thường (Should-have). TODO Week 6 nếu còn thời gian."""
    del telemetry
    return DetectResponse(anomaly=False, reason=None)
