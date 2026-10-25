"""
Sinh quỹ đạo robot "vào hàng ray -> đi và dừng làm việc -> quay ra" (mục 6.2).

Bố trí nhà kính 100 × 50 m (trục x dọc cạnh dài):
- Lối chính: dải y ∈ [0; AISLE_WIDTH], robot chạy trên đường tâm y = AISLE_Y.
- Hàng ray: vuông góc lối chính, x = 0,9 + 1,8·k, từ y = AISLE_WIDTH tới
  AISLE_WIDTH + RAIL_LENGTH (45 m).
- Gateway cố định ở giữa lối chính (50; AISLE_Y).

Mỗi robot phụ trách một dải hàng ray liền nhau. Trong một hàng: đi vào với tốc
độ ray, cứ k mét dừng U(15; 24) s; tới cuối hàng thì lùi ra (không dừng), lên
lối chính, sang hàng kế tiếp; hết dải thì quay về hàng đầu dải. Để robot không
cùng pha, mỗi robot bắt đầu ở một hàng ngẫu nhiên trong dải, tại một vị trí
ngẫu nhiên đang đi vào hàng.

Đầu ra contracts/waypoints/<số robot>_<seed>[_<tag>].csv với cột
node_id, t_s, x_m, y_m (node_id = 1..N, robot "r<node_id>"). Nạp vào
WaypointMobilityModel; một lần dừng là hai waypoint liên tiếp cùng tọa độ.

Chạy: python scripts/gen_waypoints.py              (mọi số robot × seed 1..10)
      python scripts/gen_waypoints.py --nodes 10 --seeds 1 --rail-speed 1 --tag v1
"""
import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "contracts" / "waypoints"

GREENHOUSE_X = 100.0
GREENHOUSE_Y = 50.0
AISLE_WIDTH = 5.0
AISLE_Y = AISLE_WIDTH / 2
RAIL_LENGTH = 45.0
RAIL_SPACING = 1.8
RAIL_FIRST_X = RAIL_SPACING / 2
RAIL_COUNT = int((GREENHOUSE_X - RAIL_FIRST_X) // RAIL_SPACING) + 1  # 56 hàng
GATEWAY = (GREENHOUSE_X / 2, AISLE_Y)

# Sai số so sánh tọa độ khi kiểm tra waypoint nằm trên lối/ray.
EPS = 1e-6


@dataclass
class Params:
    duration_s: float = 900.0
    rail_speed: float = 0.2
    aisle_speed: float = 0.5
    stop_every_m: float = 2.0
    stop_min_s: float = 15.0
    stop_max_s: float = 24.0


@dataclass
class Track:
    """Quỹ đạo của một robot dưới dạng chuỗi waypoint (t, x, y)."""

    points: list[tuple[float, float, float]] = field(default_factory=list)

    @property
    def t(self) -> float:
        return self.points[-1][0]

    @property
    def pos(self) -> tuple[float, float]:
        return self.points[-1][1], self.points[-1][2]

    def move_to(self, x: float, y: float, speed: float) -> None:
        x0, y0 = self.pos
        dist = math.hypot(x - x0, y - y0)
        if dist > EPS:
            self.points.append((self.t + dist / speed, x, y))

    def wait(self, seconds: float) -> None:
        x, y = self.pos
        self.points.append((self.t + seconds, x, y))


def rail_x(index: int) -> float:
    return RAIL_FIRST_X + RAIL_SPACING * index


def rail_strips(n_robots: int) -> list[list[int]]:
    """Chia các hàng ray thành n dải liền nhau, chênh lệch tối đa 1 hàng."""
    base, extra = divmod(RAIL_COUNT, n_robots)
    strips, start = [], 0
    for i in range(n_robots):
        size = base + (1 if i < extra else 0)
        strips.append(list(range(start, start + size)))
        start += size
    return strips


def work_rail(track: Track, x: float, start_depth: float, p: Params, rng: random.Random) -> None:
    """Đi vào hàng từ độ sâu start_depth, dừng mỗi k mét, tới cuối rồi lùi ra lối chính."""
    y_start = AISLE_WIDTH
    depth = start_depth
    # Điểm dừng kế tiếp là bội số của k tính từ đầu hàng.
    next_stop = (math.floor(depth / p.stop_every_m + EPS) + 1) * p.stop_every_m
    while next_stop <= RAIL_LENGTH + EPS:
        track.move_to(x, y_start + next_stop, p.rail_speed)
        track.wait(rng.uniform(p.stop_min_s, p.stop_max_s))
        depth = next_stop
        next_stop += p.stop_every_m
        if track.t >= p.duration_s:
            return
    track.move_to(x, y_start + RAIL_LENGTH, p.rail_speed)
    track.move_to(x, y_start, p.rail_speed)  # lùi ra, không dừng
    track.move_to(x, AISLE_Y, p.aisle_speed)


def robot_track(strip: list[int], p: Params, rng: random.Random) -> Track:
    pos_in_strip = rng.randrange(len(strip))
    x = rail_x(strip[pos_in_strip])
    start_depth = rng.uniform(0, RAIL_LENGTH)
    track = Track([(0.0, x, AISLE_WIDTH + start_depth)])
    while True:
        work_rail(track, x, start_depth, p, rng)
        if track.t >= p.duration_s:
            break
        pos_in_strip = (pos_in_strip + 1) % len(strip)
        x = rail_x(strip[pos_in_strip])
        track.move_to(x, AISLE_Y, p.aisle_speed)
        track.move_to(x, AISLE_WIDTH, p.aisle_speed)
        start_depth = 0.0
    return track


def generate(n_robots: int, seed: int, p: Params) -> dict[int, Track]:
    # Seed riêng cho từng (số robot, seed) để các file độc lập và tái tạo được.
    rng = random.Random(f"caar-waypoints-{n_robots}-{seed}")
    strips = rail_strips(n_robots)
    return {i + 1: robot_track(strips[i], p, rng) for i in range(n_robots)}


def on_layout(x: float, y: float) -> bool:
    """Waypoint phải nằm trên lối chính hoặc trên một hàng ray, trong nhà kính."""
    if not (-EPS <= x <= GREENHOUSE_X + EPS and -EPS <= y <= GREENHOUSE_Y + EPS):
        return False
    if y <= AISLE_WIDTH + EPS:
        return True
    k = round((x - RAIL_FIRST_X) / RAIL_SPACING)
    return 0 <= k < RAIL_COUNT and abs(rail_x(k) - x) < EPS and y <= AISLE_WIDTH + RAIL_LENGTH + EPS


def validate(tracks: dict[int, Track], p: Params) -> None:
    for node_id, track in tracks.items():
        times = [pt[0] for pt in track.points]
        if any(b < a for a, b in pairwise(times)):
            raise ValueError(f"robot {node_id}: time goes backwards")
        if track.t < p.duration_s:
            raise ValueError(f"robot {node_id}: track ends before {p.duration_s} s")
        for t, x, y in track.points:
            if not on_layout(x, y):
                raise ValueError(f"robot {node_id}: ({x}, {y}) at t={t} is off rails/aisle")
        # Đoạn đi giữa hai waypoint phải song song trục (trên ray hoặc trên lối).
        for (_, x0, y0), (_, x1, y1) in pairwise(track.points):
            if abs(x1 - x0) > EPS and abs(y1 - y0) > EPS:
                raise ValueError(f"robot {node_id}: diagonal move ({x0},{y0})->({x1},{y1})")
            if abs(x1 - x0) > EPS and max(y0, y1) > AISLE_WIDTH + EPS:
                raise ValueError(f"robot {node_id}: lateral move outside main aisle")


def write_csv(path: Path, tracks: dict[int, Track]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["node_id", "t_s", "x_m", "y_m"])
        for node_id, track in tracks.items():
            for t, x, y in track.points:
                w.writerow([node_id, f"{t:.3f}", f"{x:.3f}", f"{y:.3f}"])


def write_layout(out_dir: Path, p: Params) -> None:
    layout = {
        "greenhouse_m": [GREENHOUSE_X, GREENHOUSE_Y],
        "aisle": {"y_min": 0.0, "y_max": AISLE_WIDTH, "path_y": AISLE_Y},
        "rails": {
            "count": RAIL_COUNT,
            "first_x": RAIL_FIRST_X,
            "spacing_m": RAIL_SPACING,
            "y_start": AISLE_WIDTH,
            "length_m": RAIL_LENGTH,
        },
        "gateway_xy": list(GATEWAY),
        "default_params": p.__dict__,
    }
    (out_dir / "layout.json").write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh quỹ đạo robot nhà kính (mục 6.2)")
    parser.add_argument("--nodes", type=int, nargs="+", default=[6, 10, 16, 20])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--duration", type=float, default=900.0)
    parser.add_argument("--rail-speed", type=float, default=0.2)
    parser.add_argument("--aisle-speed", type=float, default=0.5)
    parser.add_argument("--stop-every", type=float, default=2.0, help="k (m)")
    parser.add_argument("--tag", default="", help="hậu tố tên file cho biến thể tham số")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    p = Params(
        duration_s=args.duration,
        rail_speed=args.rail_speed,
        aisle_speed=args.aisle_speed,
        stop_every_m=args.stop_every,
    )
    suffix = f"_{args.tag}" if args.tag else ""
    for n in args.nodes:
        for seed in args.seeds:
            tracks = generate(n, seed, p)
            validate(tracks, p)
            write_csv(args.out_dir / f"{n}_{seed}{suffix}.csv", tracks)
    if not args.tag:
        write_layout(args.out_dir, p)
    print(f"wrote {len(args.nodes) * len(args.seeds)} files to {args.out_dir}")


if __name__ == "__main__":
    main()
