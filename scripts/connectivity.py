"""
Kết nối hình học: tỷ lệ thời gian robot có đường (một hay nhiều hop) về Gateway.

Mỗi giây trong 900 s, đặt robot theo quỹ đạo contracts/waypoints/<N>_<seed>.csv (nội suy tuyến
tính giữa hai waypoint, như WaypointMobilityModel của ns-3), nối hai node khi khoảng cách
≤ link_range_m trong contracts/channel.json, rồi đếm robot nằm cùng thành phần liên thông với
Gateway (vị trí trong layout.json). Chỉ xét hình học: không có shadowing, tranh chấp kênh hay
AODV, nên đây là cận trên của khả năng định tuyến.

Chạy: python scripts/connectivity.py                       # 6, 10, 16, 20 robot × seed 1..10
      python scripts/connectivity.py --nodes 10 --seeds 1 2 3
"""
import argparse
import csv
import json
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAYPOINTS = ROOT / "contracts" / "waypoints"
CHANNEL = ROOT / "contracts" / "channel.json"

Track = list[tuple[float, float, float]]  # (t_s, x_m, y_m), tăng dần theo t


def load_tracks(path: Path) -> dict[int, Track]:
    tracks: dict[int, Track] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tracks[int(r["node_id"])].append((float(r["t_s"]), float(r["x_m"]), float(r["y_m"])))
    return dict(tracks)


def position(track: Track, t: float) -> tuple[float, float]:
    i = bisect_right([p[0] for p in track], t) - 1
    if i < 0:
        return track[0][1:]
    if i >= len(track) - 1:
        return track[-1][1:]
    t0, x0, y0 = track[i]
    t1, x1, y1 = track[i + 1]
    a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return x0 + a * (x1 - x0), y0 + a * (y1 - y0)


def connected_robots(gateway: tuple[float, float], robots: list[tuple[float, float]], range_m: float) -> int:
    """Số robot có đường về Gateway trong đồ thị đĩa đơn vị bán kính range_m."""
    nodes = [gateway, *robots]
    reached = {0}
    frontier = [0]
    while frontier:
        ux, uy = nodes[frontier.pop()]
        for v, (vx, vy) in enumerate(nodes):
            if v not in reached and (ux - vx) ** 2 + (uy - vy) ** 2 <= range_m**2:
                reached.add(v)
                frontier.append(v)
    return len(reached) - 1


def connectivity(tracks: dict[int, Track], gateway: tuple[float, float], range_m: float,
                 duration_s: float = 900.0, step_s: float = 1.0) -> float:
    """Tỷ lệ (robot × thời điểm) có đường về Gateway, lấy mẫu t = 0, step, ... < duration."""
    ok = total = 0
    steps = int(duration_s / step_s)
    for k in range(steps):
        t = k * step_s
        robots = [position(tracks[i], t) for i in sorted(tracks)]
        ok += connected_robots(gateway, robots, range_m)
        total += len(robots)
    return ok / total


def main() -> None:
    parser = argparse.ArgumentParser(description="Tỷ lệ thời gian robot có đường về Gateway (hình học)")
    parser.add_argument("--nodes", type=int, nargs="+", default=[6, 10, 16, 20])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--step", type=float, default=1.0, help="bước lấy mẫu (s)")
    args = parser.parse_args()

    range_m = json.loads(CHANNEL.read_text(encoding="utf-8"))["link_range_m"]
    gx, gy = json.loads((WAYPOINTS / "layout.json").read_text(encoding="utf-8"))["gateway_xy"]
    print(f"Tầm liên kết {range_m} m, Gateway ({gx}, {gy}), seed {args.seeds}")
    print()
    print("| Robot / 1 ha | Có đường về Gateway | Theo từng seed |")
    print("|---|---|---|")
    for n in args.nodes:
        shares = [connectivity(load_tracks(WAYPOINTS / f"{n}_{s}.csv"), (gx, gy), range_m, step_s=args.step)
                  for s in args.seeds]
        mean = sum(shares) / len(shares)
        print(f"| {n} | {100 * mean:.0f} % | " + ", ".join(f"{100 * s:.0f}" for s in shares) + " |")


if __name__ == "__main__":
    main()
