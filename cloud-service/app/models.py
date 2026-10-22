"""Pydantic request/response models cho CAAR Cloud Service (tài liệu đồ án, mục 9.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

# Sai số cho phép khi kiểm tra tổng trọng số bằng 1.
WEIGHT_SUM_TOLERANCE = 0.001


class NodeTelemetry(BaseModel):
    """Telemetry định tuyến của một robot, do Gateway gom lại."""

    # node_id là chuỗi (ví dụ "r1"); gửi số sẽ bị 422.
    node_id: StrictStr = Field(min_length=1, max_length=64)
    rssi_avg: float = Field(ge=-120, le=0, allow_inf_nan=False)
    energy_remaining_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    hop_count: int = Field(ge=1)


class NetworkSnapshot(BaseModel):
    """Trạng thái toàn mạng Gateway gửi lên /optimize mỗi chu kỳ T."""

    run_id: int
    # Unix time lúc Gateway tạo snapshot; lệch quá 30 s bị từ chối (security.py).
    timestamp: float = Field(allow_inf_nan=False)
    # Tùy chọn: nếu có, mỗi nonce chỉ được dùng một lần.
    nonce: str | None = Field(default=None, min_length=1, max_length=128)
    nodes: list[NodeTelemetry] = Field(min_length=1)


class Weights(BaseModel):
    """Ba trọng số cloud điều chỉnh: hop, sóng, pin."""

    model_config = ConfigDict(frozen=True)

    hop_weight: float = Field(ge=0, allow_inf_nan=False)
    rssi_weight: float = Field(ge=0, allow_inf_nan=False)
    energy_weight: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _sum_is_one(self) -> "Weights":
        total = self.hop_weight + self.rssi_weight + self.energy_weight
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"weights must sum to 1 (got {total})")
        return self


class OptimizeResponse(BaseModel):
    weights: Weights
    rule: Literal["low_battery", "poor_signal", "balanced"]
