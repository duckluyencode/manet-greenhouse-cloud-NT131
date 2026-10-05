import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .db import init_db
from .models import DetectResponse, OptimizeResponse, TelemetrySnapshot


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Khởi tạo database khi service bắt đầu."""
    init_db()
    yield


app = FastAPI(
    title="CAAR Cloud-Service",
    version="0.1.0",
    lifespan=lifespan,
)

# Các ngưỡng này giới hạn tuổi request và mức lệch timestamp cho phép.
MAX_AGE_SECONDS = 15
MAX_FUTURE_SKEW_SECONDS = 5
# Giới hạn cache nonce để tránh dùng hết bộ nhớ khi nhận quá nhiều request.
MAX_SEEN_NONCES = 100_000
# Tần suất quét nonce hết hạn trong bộ nhớ.
NONCE_CLEANUP_INTERVAL_SECONDS = 5

# Cache nonce trong tiến trình hiện tại; triển khai nhiều worker cần kho dùng chung.
SEEN_NONCES: dict[str, float] = {}
# Khóa đảm bảo thao tác kiểm tra và ghi nonce không bị race trong cùng tiến trình.
_NONCE_LOCK = threading.Lock()
# Mốc thời gian lần gần nhất đã dọn nonce hết hạn.
_last_nonce_cleanup = 0.0


def validate_freshness(telemetry: TelemetrySnapshot) -> None:
    """Từ chối telemetry cũ/lệch tương lai và chỉ chấp nhận mỗi nonce một lần."""
    global _last_nonce_cleanup

    now = time.time()
    age = now - telemetry.timestamp
    if age > MAX_AGE_SECONDS or age < -MAX_FUTURE_SKEW_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="Request timestamp is outside the allowed time window",
        )

    with _NONCE_LOCK:
        if now - _last_nonce_cleanup >= NONCE_CLEANUP_INTERVAL_SECONDS:
            expired_nonces = [
                nonce for nonce, expires_at in SEEN_NONCES.items()
                if expires_at < now
            ]
            for nonce in expired_nonces:
                del SEEN_NONCES[nonce]
            _last_nonce_cleanup = now

        expires_at = SEEN_NONCES.get(telemetry.nonce)
        if expires_at is not None and expires_at >= now:
            raise HTTPException(
                status_code=400,
                detail="Duplicate nonce replay detected",
            )
        if expires_at is not None:
            del SEEN_NONCES[telemetry.nonce]

        if len(SEEN_NONCES) >= MAX_SEEN_NONCES:
            raise HTTPException(
                status_code=503,
                detail="Replay protection is temporarily at capacity",
            )

        # Keep each nonce until its timestamp can no longer pass freshness checks.
        SEEN_NONCES[telemetry.nonce] = (
            telemetry.timestamp + MAX_AGE_SECONDS
        )


@app.get("/health")
def health() -> dict:
    """Endpoint kiểm tra service đang hoạt động."""
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(telemetry: TelemetrySnapshot) -> OptimizeResponse:
    """
    Nhánh (a) — tối ưu hiệu năng 

    TODO (Week 3-4, Owner B): thay công thức placeholder bằng
    weighted heuristic thật (RSSI + hop-count + năng lượng còn lại).
    """
    # Kiểm tra freshness trước khi tính toán hoặc trả kết quả.
    validate_freshness(telemetry)
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
    # Endpoint detect dùng chung cơ chế chống request cũ và request bị phát lại.
    validate_freshness(telemetry)
    return DetectResponse(anomaly=False, reason=None)
