"""
Nhập kết quả mô phỏng NS-3 và trace WAN vào SQLite (mục 9.4, hợp đồng 12.3).

Mỗi file results/raw/*.csv (trừ wan_trace.csv và *_events.csv) có một hoặc
nhiều dòng với các cột:
    config_type, scenario, seed, node_count, mobility_speed, params,
    pdr, avg_delay_ms, p95_delay_ms, overhead_ratio, route_discovery_ms,
    min_energy_pct, cloud_bandwidth_bytes,
    loss_no_route_ratio, hops_avg, link_rssi_avg_dbm, weak_relay_share
4 cột cuối (đo cơ chế định tuyến) có thể thiếu ở kết quả cũ; khi đó ghi NULL.
params là chuỗi JSON (ví dụ {"dmax_ms": 20, "ttl_s": 60}). Script đọc thông
tin run từ nội dung file, không dựa vào tên file.

File <tên>_events.csv đi kèm (tùy chọn): ts, event_type, payload — log
param_update / outage_start / stale_detected / outage_end của Gateway.

Run đã nhập (cùng config, scenario, seed, số robot, tốc độ, params) bị bỏ qua.

Chạy: python scripts/import_ns3_results.py --raw results/raw --db results/results.db
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud-service"))

from app import db  # noqa: E402

RUN_COLUMNS = ("config_type", "scenario", "seed", "node_count", "mobility_speed", "params")
CONFIGS = {"no_cloud", "local_optimized", "gateway_heuristic", "cloud_assisted"}
# Cột thêm sau, không bắt buộc với file kết quả cũ.
OPTIONAL_METRICS = ("loss_no_route_ratio", "hops_avg", "link_rssi_avg_dbm", "weak_relay_share")


def _num(value: str) -> float | None:
    return None if value is None or value.strip() == "" else float(value)


def parse_row(row: dict[str, str], source: Path) -> tuple[dict, dict]:
    required = [c for c in RUN_COLUMNS + db.METRIC_COLUMNS if c not in OPTIONAL_METRICS]
    missing = [c for c in required if c not in row]
    if missing:
        raise ValueError(f"{source}: missing columns {missing}")
    if row["config_type"] not in CONFIGS:
        raise ValueError(f"{source}: unknown config_type {row['config_type']!r}")
    run = {
        "config_type": row["config_type"],
        "scenario": row["scenario"],
        "seed": int(row["seed"]),
        "node_count": int(row["node_count"]),
        "mobility_speed": float(row["mobility_speed"]),
        "params": json.loads(row["params"] or "{}"),
    }
    metrics = {c: _num(row.get(c)) for c in db.METRIC_COLUMNS}
    if metrics["cloud_bandwidth_bytes"] is not None:
        metrics["cloud_bandwidth_bytes"] = int(metrics["cloud_bandwidth_bytes"])
    if metrics["pdr"] is not None and not 0 <= metrics["pdr"] <= 1:
        raise ValueError(f"{source}: pdr {metrics['pdr']} outside [0, 1]")
    return run, metrics


def import_events(path: Path, run_id: int) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        db.save_cloud_event(run_id, r["event_type"], r.get("payload", ""), ts=r["ts"])
    return len(rows)


def import_results(raw_dir: Path) -> tuple[int, int]:
    imported = skipped = 0
    for path in sorted(raw_dir.glob("*.csv")):
        if path.name == "wan_trace.csv" or path.stem.endswith("_events"):
            continue
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            run, metrics = parse_row(row, path)
            if db.find_run(**run) is not None:
                skipped += 1
                continue
            run_id = db.save_run(**run)
            db.save_metrics(run_id, **metrics)
            events = path.with_name(f"{path.stem}_events.csv")
            if events.exists() and len(rows) == 1:
                import_events(events, run_id)
            imported += 1
    return imported, skipped


def import_wan_trace(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [
            (float(r["ts"]), float(r["rtt_ms"]), int(r["http_status"]), int(r["timeout"]))
            for r in csv.DictReader(f)
        ]
    with db.get_conn() as conn:
        conn.execute("DELETE FROM wan_trace")  # trace nhập lại thì thay toàn bộ
    conn.close()
    return db.save_wan_samples(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhập CSV kết quả NS-3 vào SQLite")
    parser.add_argument("--raw", type=Path, default=ROOT / "results" / "raw")
    parser.add_argument("--db", type=Path, default=ROOT / "results" / "results.db")
    parser.add_argument("--wan-trace", type=Path, help="wan_trace.csv để nhập vào bảng wan_trace")
    args = parser.parse_args()

    os.environ["CAAR_DB_PATH"] = str(args.db)
    db.init_db()
    imported, skipped = import_results(args.raw)
    print(f"runs: {imported} imported, {skipped} already in {args.db}")
    if args.wan_trace:
        print(f"wan_trace: {import_wan_trace(args.wan_trace)} rows")


if __name__ == "__main__":
    main()
