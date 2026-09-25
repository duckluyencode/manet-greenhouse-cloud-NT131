"""
Cloud-Service — "bo nao" toi uu cho kien truc Cloud-Assisted Adaptive Routing (CAAR).

Endpoints:
- GET  /health    : kiem tra service con song
- POST /optimize  : nhan telemetry, tra ve trong so dinh tuyen moi (nhanh a - Must-have)
- POST /detect    : nhan telemetry, tra canh bao bat thuong (nhanh b - Should-have)

Owner: B (Cloud/Backend Lead) — xem Master Plan Section 2, 12.3
"""
from fastapi import FastAPI

from app.db import init_db
from app.models import DetectResponse, OptimizeResponse, TelemetrySnapshot
from app.twin import predict_effect

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
    Nhanh (a) - toi uu hieu nang (Must-have).

    TODO (Week 3-4, Owner B, Master Plan Day 18/24): thay cong thuc
    placeholder duoi day bang logic weighted heuristic that (RSSI +
    hop-count + nang luong con lai).
    """
    candidate_weights = _compute_candidate_weights(telemetry)

    # TODO (Week 6-7, Owner B, Should-have, Master Plan Section 1.1):
    # bat digital-twin validation o day khi da huan luyen model that.
    # prediction = predict_effect(telemetry, candidate_weights)
    # if prediction.worse_than_current and telemetry.last_known_weights:
    #     return OptimizeResponse(
    #         weights=telemetry.last_known_weights, twin_rejected=True
    #     )

    return OptimizeResponse(weights=candidate_weights, twin_rejected=False)


def _compute_candidate_weights(telemetry: TelemetrySnapshot) -> dict:
    """Placeholder - cong thuc that se them o Week 3-4 (Master Plan Day 18, 24)."""
    del telemetry  # chua dung toi, se dung khi cai logic that
    return {"rssi_weight": 0.5, "energy_weight": 0.3, "hop_weight": 0.2}


@app.post("/detect", response_model=DetectResponse)
def detect(telemetry: TelemetrySnapshot) -> DetectResponse:
    """Nhanh (b) - phat hien bat thuong (Should-have). TODO Week 6 neu con thoi gian."""
    del telemetry
    return DetectResponse(anomaly=False, reason=None)
