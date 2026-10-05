"""
SQLite schema cho CAAR Cloud Service.

Bảng:
- runs          : metadata mỗi lần chạy mô phỏng (config_type, scenario, seed...)
- metrics       : kết quả đo lường của 1 run (PDR, delay, overhead, energy...)
- cloud_events  : log sự kiện trên kênh cloud (param_update, outage, twin_rejected...)
"""
import sqlite3
from pathlib import Path
from typing import Any

# Đường dẫn file SQLite mặc định của Cloud Service.
DB_PATH = Path(__file__).resolve().parent.parent / "results.db"


def get_conn() -> sqlite3.Connection:
    """Mở kết nối SQLite tới cơ sở dữ liệu của service."""
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Tạo các bảng lưu kết quả mô phỏng và sự kiện nếu chưa tồn tại."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL,      -- no_cloud | local_optimized | cloud_assisted
            scenario TEXT NOT NULL,          -- baseline | outage | degraded_latency |
                                              -- packet_loss | gateway_spof | stale_params |
                                              -- mitm | scale_sweep | growth_stage_sweep
            seed INTEGER,
            node_count INTEGER,
            mobility_speed REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            run_id INTEGER REFERENCES runs(id),
            pdr REAL,
            avg_delay_ms REAL,
            p95_delay_ms REAL,
            overhead_ratio REAL,
            energy_total_j REAL,
            energy_gateway_j REAL,
            network_lifetime_s REAL,
            cloud_latency_ms REAL,
            cloud_bandwidth_bytes INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cloud_events (
            run_id INTEGER REFERENCES runs(id),
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT,   -- param_update | outage_start | outage_end |
                                -- stale_detected | twin_rejected
            payload TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_run(
    config_type: str,
    scenario: str,
    seed: int,
    node_count: int,
    mobility_speed: float,
) -> int:
    """Lưu metadata của một lần chạy và trả về ID được SQLite tạo."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO runs (config_type, scenario, seed, node_count, mobility_speed)
           VALUES (?, ?, ?, ?, ?)""",
        (config_type, scenario, seed, node_count, mobility_speed),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    assert run_id is not None
    return run_id


def save_metrics(run_id: int, **metrics: Any) -> None:
    """Lưu các chỉ số đo được gắn với một lần chạy."""
    conn = get_conn()
    cols = ", ".join(metrics.keys())
    placeholders = ", ".join(["?"] * len(metrics))
    conn.execute(
        f"INSERT INTO metrics (run_id, {cols}) VALUES (?, {placeholders})",
        (run_id, *metrics.values()),
    )
    conn.commit()
    conn.close()


def save_cloud_event(run_id: int, event_type: str, payload: str = "") -> None:
    """Lưu một sự kiện phát sinh trong quá trình service hoạt động."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO cloud_events (run_id, event_type, payload) VALUES (?, ?, ?)",
        (run_id, event_type, payload),
    )
    conn.commit()
    conn.close()
