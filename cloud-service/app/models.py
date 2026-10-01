"""Pydantic request/response models cho CAAR Cloud Service."""

from pydantic import BaseModel


class TelemetrySnapshot(BaseModel):
    """Dữ liệu telemetry mà Gateway gửi lên từ MANET."""

    node_id: str
    rssi_avg: float
    energy_remaining_pct: float
    hop_count: int
    last_known_weights: dict[str, float] | None = None


class OptimizeResponse(BaseModel):
    weights: dict[str, float]
    twin_rejected: bool = False


class DetectResponse(BaseModel):
    anomaly: bool
    reason: str | None = None
