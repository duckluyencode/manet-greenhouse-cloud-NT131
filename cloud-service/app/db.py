"""
SQLite schema cho CAAR Cloud Service (tài liệu đồ án, mục 9.4).

Bảng:
- runs          : metadata mỗi lần chạy mô phỏng (config_type, scenario, seed, params JSON)
- metrics       : kết quả đo của 1 run (PDR, độ trễ, overhead, tìm đường, pin thấp nhất...)
- cloud_events  : log sự kiện kênh cloud (param_update, outage_start, stale_detected, outage_end)
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

# Đường dẫn file SQLite; ghi đè bằng biến môi trường CAAR_DB_PATH (Docker, test).
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "results.db"

METRIC_COLUMNS = (
    "pdr",
    "avg_delay_ms",
    "p95_delay_ms",
    "overhead_ratio",
    "route_discovery_ms",
    "min_energy_pct",
    "cloud_bandwidth_bytes",
    "loss_no_route_ratio",
    "hops_avg",
    "link_rssi_avg_dbm",
    "weak_relay_share",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_type TEXT NOT NULL,   -- no_cloud | local_optimized | gateway_heuristic | cloud_assisted
    scenario TEXT NOT NULL,      -- baseline | outage | stale | scale | sensitivity
    seed INTEGER,
    node_count INTEGER,
    mobility_speed REAL,
    params TEXT,                 -- JSON: dmax_ms, ttl_s, outage_start_s, outage_end_s...
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS metrics (
    run_id INTEGER REFERENCES runs(id),
    pdr REAL,
    avg_delay_ms REAL,
    p95_delay_ms REAL,
    overhead_ratio REAL,
    route_discovery_ms REAL,
    min_energy_pct REAL,
    cloud_bandwidth_bytes INTEGER,
    loss_no_route_ratio REAL,    -- gói dữ liệu bỏ vì không có đường / gói gửi
    hops_avg REAL,               -- số hop trung bình của gói tới Gateway
    link_rssi_avg_dbm REAL,      -- RSSI trung bình các link đã chở dữ liệu
    weak_relay_share REAL        -- tỷ lệ lượt chuyển tiếp do robot pin < 30 %
);
CREATE TABLE IF NOT EXISTS cloud_events (
    run_id INTEGER REFERENCES runs(id),
    ts TEXT DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,             -- param_update | outage_start | stale_detected | outage_end
    payload TEXT
);
"""

# Cột thêm so với bản cũ; DB tạo từ bản cũ được bổ sung khi init_db().
_ADDED_COLUMNS = {
    "runs": {"params": "TEXT"},
    "metrics": {
        "route_discovery_ms": "REAL",
        "min_energy_pct": "REAL",
        "loss_no_route_ratio": "REAL",
        "hops_avg": "REAL",
        "link_rssi_avg_dbm": "REAL",
        "weak_relay_share": "REAL",
    },
}


def db_path() -> Path:
    return Path(os.environ.get("CAAR_DB_PATH", DEFAULT_DB_PATH))


def get_conn() -> sqlite3.Connection:
    """Mở kết nối SQLite tới cơ sở dữ liệu của service."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db() -> None:
    """Tạo các bảng nếu chưa có và bổ sung cột mới cho DB tạo từ bản cũ."""
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        for table, columns in _ADDED_COLUMNS.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
    conn.close()


def save_run(
    config_type: str,
    scenario: str,
    seed: int,
    node_count: int,
    mobility_speed: float,
    params: dict[str, Any] | None = None,
) -> int:
    """Lưu metadata của một lần chạy và trả về ID được SQLite tạo."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO runs
               (config_type, scenario, seed, node_count, mobility_speed, params)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                config_type,
                scenario,
                seed,
                node_count,
                mobility_speed,
                json.dumps(params or {}, sort_keys=True),
            ),
        )
        run_id = cur.lastrowid
    conn.close()
    assert run_id is not None
    return run_id


def find_run(
    config_type: str,
    scenario: str,
    seed: int,
    node_count: int,
    mobility_speed: float,
    params: dict[str, Any] | None = None,
) -> int | None:
    """Tìm run đã nhập có cùng cấu hình (để script nhập không nhập trùng)."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id FROM runs WHERE config_type = ? AND scenario = ? AND seed = ?
               AND node_count = ? AND mobility_speed = ? AND params = ?""",
            (
                config_type,
                scenario,
                seed,
                node_count,
                mobility_speed,
                json.dumps(params or {}, sort_keys=True),
            ),
        ).fetchone()
    conn.close()
    return row[0] if row else None


def save_metrics(run_id: int, **metrics: Any) -> None:
    """Lưu các chỉ số đo được gắn với một lần chạy."""
    unknown = set(metrics) - set(METRIC_COLUMNS)
    if unknown:
        raise ValueError(f"unknown metric columns: {sorted(unknown)}")
    cols = ", ".join(metrics.keys())
    placeholders = ", ".join(["?"] * len(metrics))
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO metrics (run_id, {cols}) VALUES (?, {placeholders})",
            (run_id, *metrics.values()),
        )
    conn.close()


def save_cloud_event(
    run_id: int, event_type: str, payload: str = "", ts: str | None = None
) -> None:
    """Lưu một sự kiện của kênh cloud; ts mặc định là thời điểm ghi."""
    with get_conn() as conn:
        if ts is None:
            conn.execute(
                "INSERT INTO cloud_events (run_id, event_type, payload) VALUES (?, ?, ?)",
                (run_id, event_type, payload),
            )
        else:
            conn.execute(
                "INSERT INTO cloud_events (run_id, ts, event_type, payload)"
                " VALUES (?, ?, ?, ?)",
                (run_id, ts, event_type, payload),
            )
    conn.close()




def metrics_summary() -> list[dict[str, Any]]:
    """PDR và độ trễ trung bình theo cấu hình và kịch bản (cho /metrics/summary)."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT r.config_type, r.scenario, COUNT(*) AS runs,
                      AVG(m.pdr) AS pdr_mean, AVG(m.avg_delay_ms) AS avg_delay_ms_mean
               FROM runs r JOIN metrics m ON r.id = m.run_id
               GROUP BY r.config_type, r.scenario
               ORDER BY r.scenario, r.config_type"""
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
