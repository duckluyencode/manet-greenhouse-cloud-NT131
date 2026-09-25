"""Pydantic request/response models cho Cloud-Service."""
from typing import Dict, Optional

from pydantic import BaseModel


class TelemetrySnapshot(BaseModel):
    """Du lieu telemetry ma Gateway gui len tu MANET."""

    node_id: str
    rssi_avg: float
    energy_remaining_pct: float
    hop_count: int
    last_known_weights: Optional[Dict[str, float]] = None


class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    twin_rejected: bool = False


class DetectResponse(BaseModel):
    anomaly: bool
    reason: Optional[str] = None
