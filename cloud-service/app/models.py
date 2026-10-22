"""Pydantic request/response models cho CAAR Cloud Service."""

from pydantic import BaseModel, Field


# Schema request nhận dữ liệu trạng thái mạng từ Gateway.
class TelemetrySnapshot(BaseModel):
    """Dữ liệu telemetry mà Gateway gửi lên từ MANET."""

    # Các chỉ số đầu vào dùng cho việc chọn trọng số định tuyến.
    node_id: str
    rssi_avg: float
    energy_remaining_pct: float
    hop_count: int
    last_known_weights: dict[str, float] | None = None

    timestamp: float = Field(allow_inf_nan=False)  # cho biết request được tạo lúc nào
    nonce: str = Field(min_length=1, max_length=128)  # mã dùng một lần cho mỗi request, để tránh replay attack


# Schema phản hồi chứa trọng số định tuyến và kết quả kiểm tra Digital Twin.
class OptimizeResponse(BaseModel):
    weights: dict[str, float]
    twin_rejected: bool = False


# Schema phản hồi của endpoint phát hiện bất thường.
class DetectResponse(BaseModel):
    anomaly: bool
    reason: str | None = None
