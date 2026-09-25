"""
Digital-Twin validation layer (Should-have - Master Plan Section 1.1, Week 6-7).

Hien tai la stub: predict_effect() tra ve gia tri placeholder, luon coi
la "khong te hon" de khong chan nham truoc khi co model that.

TODO (Owner B, Week 6-7): huan luyen 1 model hoi quy nhe (vi du sklearn
LinearRegression hoac DecisionTreeRegressor) tu du lieu bang `metrics`
da thu thap o Week 6 (xem app/db.py), du doan PDR/delay tu (telemetry
hien tai + trong so ung vien), dung de quyet dinh twin_rejected trong
main.py::optimize(). Day chinh la co che kiem chung cho RQ6/H6 va
Kich ban S4 mo rong trong ieee-paper-draft.md.
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
    """Placeholder - chua huan luyen model that."""
    del telemetry, candidate_weights
    return TwinPrediction(
        predicted_pdr=1.0, predicted_delay_ms=0.0, worse_than_current=False
    )
