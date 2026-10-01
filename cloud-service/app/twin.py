"""
Digital-Twin validation layer (Should-have — Week 6-7).

Hiện tại là stub: predict_effect() trả giá trị placeholder, luôn coi
là "không tệ hơn" để không chặn nhầm trước khi có model thật.

TODO (Owner B, Week 6-7): huấn luyện model hồi quy nhẹ (sklearn
LinearRegression hoặc DecisionTreeRegressor) từ dữ liệu bảng `metrics`
đã thu thập ở Week 6 (xem app/db.py), dự đoán PDR/delay từ
(telemetry hiện tại + trọng số ứng viên), dùng để quyết định
twin_rejected trong main.py::optimize().
"""
from dataclasses import dataclass

from app.models import TelemetrySnapshot


@dataclass
class TwinPrediction:
    predicted_pdr: float
    predicted_delay_ms: float
    worse_than_current: bool


def predict_effect(
    telemetry: TelemetrySnapshot, candidate_weights: dict
) -> TwinPrediction:
    """Placeholder — chưa huấn luyện model thật (Week 6-7)."""
    del telemetry, candidate_weights
    return TwinPrediction(
        predicted_pdr=1.0, predicted_delay_ms=0.0, worse_than_current=False
    )
