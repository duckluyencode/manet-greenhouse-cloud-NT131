import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from . import db
from .heuristic import NodeSample, choose_weights
from .models import NetworkSnapshot, OptimizeResponse, Weights
from .security import check_freshness, require_api_key


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Khởi tạo database khi service bắt đầu."""
    db.init_db()
    yield


app = FastAPI(
    title="CAAR Cloud-Service",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    """Endpoint kiểm tra service đang hoạt động."""
    return {"status": "ok"}


@app.post(
    "/optimize",
    response_model=OptimizeResponse,
    dependencies=[Depends(require_api_key)],
)
def optimize(snapshot: NetworkSnapshot) -> OptimizeResponse:
    """Nhận NetworkSnapshot, trả 3 trọng số định tuyến cho toàn mạng (mục 7.2, 9.1)."""
    check_freshness(snapshot)

    decision = choose_weights(
        NodeSample(n.rssi_avg, n.energy_remaining_pct) for n in snapshot.nodes
    )
    response = OptimizeResponse(
        weights=Weights(
            hop_weight=decision.hop_weight,
            rssi_weight=decision.rssi_weight,
            energy_weight=decision.energy_weight,
        ),
        rule=decision.rule,
    )
    db.save_cloud_event(
        snapshot.run_id, "param_update", json.dumps(response.model_dump())
    )
    return response


@app.get("/metrics/summary", dependencies=[Depends(require_api_key)])
def metrics_summary() -> list[dict]:
    """PDR và độ trễ trung bình theo cấu hình và kịch bản đã nhập vào SQLite."""
    return db.metrics_summary()
