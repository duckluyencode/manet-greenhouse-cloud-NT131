"""
Kiểm tra tích hợp NS-3 (mục 14.3) trên một bản ns-3-dev đã cài CAAR
(simulation/install.sh + ./ns3 build). Chạy trên máy có NS-3, trong Docker hoặc CI.

Kiểm tra:
1. Cả 4 cấu hình chạy được, CSV đúng hợp đồng contracts/README.md, metric trong miền hợp lệ.
2. Cùng seed chạy hai lần cho kết quả giống hệt.
3. Mất cloud: log Gateway đúng thứ tự outage_start -> stale_detected -> outage_end,
   và không có param_update trong lúc mất cloud.
4. w_h = 1 (wr = we = 0): PDR của local_optimized nằm trong CI 95% của no_cloud
   (chỉ khi truyền --seeds >= 3, vì cần nhiều seed).
5. Kết quả nhập được vào SQLite bằng import_ns3_results.py.

Chạy: python scripts/check_ns3.py --ns3 /opt/ns-3-dev --out /tmp/caar-check [--seeds 5]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from caar_stats import summarize  # noqa: E402

CONFIGS = ["no_cloud", "local_optimized", "gateway_heuristic", "cloud_assisted"]
COLUMNS = [
    "config_type", "scenario", "seed", "node_count", "mobility_speed", "params",
    "pdr", "avg_delay_ms", "p95_delay_ms", "overhead_ratio", "route_discovery_ms",
    "min_energy_pct", "cloud_bandwidth_bytes",
]

failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("  ok   " if ok else "  FAIL ") + message)
    if not ok:
        failures.append(message)


def run_caar(ns3: Path, out: Path, config: str, seed: int, scenario: str = "baseline", *extra: str) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "caar", f"--config={config}", f"--scenario={scenario}", f"--seed={seed}", "--nodes=10",
        f"--waypoints={CONTRACTS / 'waypoints' / f'10_{seed}.csv'}",
        f"--channel={CONTRACTS / 'channel.json'}", f"--out={out}", *extra,
    ]
    start = time.monotonic()
    proc = subprocess.run(
        [str(ns3 / "ns3"), "run", "--no-build", " ".join(args)],
        cwd=ns3, capture_output=True, text=True,
    )
    elapsed = time.monotonic() - start
    if proc.returncode != 0:
        print(proc.stdout[-3000:], proc.stderr[-3000:], sep="\n")
        raise SystemExit(f"caar failed: {' '.join(args)}")
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"  ran  {config} seed={seed} {scenario} in {elapsed:.1f}s: {proc.stdout.strip().splitlines()[-1]}")
    assert len(rows) == 1, f"{out}: expected one row"
    return rows[0]


def check_row(row: dict, config: str) -> None:
    check(list(row) == COLUMNS, f"{config}: CSV columns match the contract")
    params = json.loads(row["params"])
    pdr = float(row["pdr"])
    check(0 < pdr <= 1, f"{config}: pdr {pdr:.4f} in (0, 1]")
    check(float(row["avg_delay_ms"]) > 0, f"{config}: avg_delay_ms > 0")
    check(float(row["p95_delay_ms"]) >= float(row["avg_delay_ms"]) * 0.5, f"{config}: p95 delay plausible")
    check(0 < float(row["overhead_ratio"]) < 1, f"{config}: overhead_ratio in (0, 1)")
    check(row["route_discovery_ms"] != "" and float(row["route_discovery_ms"]) > 0,
          f"{config}: route discovery time measured (RouteDiscovery trace from the AODV patch)")
    check(0 <= float(row["min_energy_pct"]) < 100, f"{config}: min_energy_pct in [0, 100)")
    cloud_bytes = int(row["cloud_bandwidth_bytes"])
    check((cloud_bytes > 0) == (config == "cloud_assisted"),
          f"{config}: cloud_bandwidth_bytes {cloud_bytes} only for cloud_assisted")
    check(params.get("pdr_window") is not None, f"{config}: params.pdr_window present")


def read_events(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm tra tích hợp NS-3 của CAAR")
    parser.add_argument("--ns3", type=Path, required=True, help="thư mục ns-3-dev đã build")
    parser.add_argument("--out", type=Path, required=True, help="thư mục ghi kết quả thử")
    parser.add_argument("--seeds", type=int, default=1, help="số seed cho phép thử w_h = 1 (>= 3 để chạy)")
    args = parser.parse_args()
    raw = args.out / "raw"

    print("1. four configurations")
    rows = {}
    for config in CONFIGS:
        rows[config] = run_caar(args.ns3, raw / f"{config}_baseline_1.csv", config, 1, "baseline",
                                "--ttl=60", "--dmax=20")
        check_row(rows[config], config)
    events = read_events(raw / "cloud_assisted_baseline_1_events.csv")
    check(any(e["event_type"] == "param_update" for e in events),
          "cloud_assisted: Gateway logged param_update")

    print("2. same seed, same result")
    again = run_caar(args.ns3, args.out / "repeat" / "no_cloud_baseline_1.csv", "no_cloud", 1, "baseline",
                     "--ttl=60", "--dmax=20")
    check(again == rows["no_cloud"], "no_cloud seed 1 run twice gives identical rows")

    print("3. cloud outage 300-600 s, TTL 60 s")
    run_caar(args.ns3, raw / "cloud_assisted_outage_1.csv", "cloud_assisted", 1, "outage",
             "--ttl=60", "--dmax=20", "--outage-start=300", "--outage-end=600")
    events = read_events(raw / "cloud_assisted_outage_1_events.csv")
    order = [e["event_type"] for e in events if e["event_type"] != "param_update"]
    check(order == ["outage_start", "stale_detected", "outage_end"],
          f"outage events in order: {order}")
    during = [e for e in events if e["event_type"] == "param_update" and 300 < float(e["ts"]) < 600]
    check(not during, "no param_update while the cloud is down")
    stale = next((float(e["ts"]) for e in events if e["event_type"] == "stale_detected"), None)
    check(stale is not None and 355 <= stale <= 365, f"stale_detected about 60 s after the outage: {stale}")

    if args.seeds >= 3:
        print(f"4. w_h = 1 behaves like AODV ({args.seeds} seeds)")
        base, hop_only = [], []
        for seed in range(1, args.seeds + 1):
            base.append(float(run_caar(args.ns3, args.out / "wh1" / f"no_cloud_{seed}.csv", "no_cloud",
                                       seed, "check", "--dmax=20")["pdr"]))
            hop_only.append(float(run_caar(args.ns3, args.out / "wh1" / f"local_optimized_{seed}.csv",
                                           "local_optimized", seed, "check", "--dmax=20",
                                           "--fixed-weights=1,0,0")["pdr"]))
        s = summarize(base)
        m = summarize(hop_only).mean
        check(s.low <= m <= s.high,
              f"PDR w_h=1 {m:.4f} within no_cloud CI [{s.low:.4f}, {s.high:.4f}]")
    else:
        print("4. w_h = 1 check skipped (use --seeds 3 or more)")

    print("5. import into SQLite")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "import_ns3_results.py"), "--raw", str(raw),
         "--db", str(args.out / "check.db")],
        capture_output=True, text=True, env=env,
    )
    print("  " + proc.stdout.strip())
    check(proc.returncode == 0 and "5 imported" in proc.stdout, "5 runs imported")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        raise SystemExit(1)
    print("all NS-3 checks passed")


if __name__ == "__main__":
    main()
