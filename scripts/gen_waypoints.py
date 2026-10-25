"""
Sinh quỹ đạo robot "vào hàng ray -> đi và dừng làm việc -> quay ra" (mục 6.2).

Bố trí nhà kính 1 ha, 100 × 100 m (docs/greenhouse-survey.md):
- Lối chính 100 m chạy dọc giữa nhà: dải y ∈ [47,5; 52,5], robot chạy trên đường
  tâm y = 50. Nhà kính đo kênh của Cama-Pinto (2019) rộng 10.000 m², hành lang
  chính 100 m.
- Hàng ray vuông góc lối chính ở cả hai phía, x = 0,9 + 1,8·k (bước 1,8 m =
  lối đi 1,2 m + hàng đôi 0,6 m), mỗi hàng dài 47,5 m: phía bắc từ y = 52,5 tới
  100, phía nam từ y = 47,5 về 0. Tổng 112 hàng.
- Gateway cố định ở giữa lối chính (50; 50).

Mỗi robot phụ trách một dải hàng ray liền nhau (thứ tự hàng: phía bắc từ trái
sang phải, rồi phía nam từ phải sang trái). Trong một hàng: đi vào với tốc độ
ray, cứ k mét dừng U(15; 24) s; tới cuối hàng thì lùi ra (không dừng), lên lối
chính, sang hàng kế tiếp; hết dải thì quay về hàng đầu dải. Để robot không
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
GREENHOUSE_Y = 100.0
AISLE_WIDTH = 5.0
AISLE_Y = GREENHOUSE_Y / 2  # đường tâm lối chính
AISLE_Y_MIN = AISLE_Y - AISLE_WIDTH / 2
AISLE_Y_MAX = AISLE_Y + AISLE_WIDTH / 2
RAIL_LENGTH = AISLE_Y_MIN  # 47,5 m mỗi phía
RAIL_SPACING = 1.8
RAIL_FIRST_X = RAIL_SPACING / 2
RAILS_PER_SIDE = int((GREENHOUSE_X - RAIL_FIRST_X) // RAIL_SPACING) + 1  # 56 hàng
RAIL_COUNT = 2 * RAILS_PER_SIDE  # 112 hàng
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


def rail_x(column: int) -> float:
    return RAIL_FIRST_X + RAIL_SPACING * column


def rail(index: int) -> tuple[float, float, int]:
    """Hàng ray thứ index: (x, y ở mép lối chính, hướng đi vào: +1 bắc, -1 nam)."""
    if index < RAILS_PER_SIDE:
        return rail_x(index), AISLE_Y_MAX, 1
    return rail_x(RAIL_COUNT - 1 - index), AISLE_Y_MIN, -1


def rail_strips(n_robots: int) -> list[list[int]]:
    """Chia các hàng ray thành n dải liền nhau, chênh lệch tối đa 1 hàng."""
    base, extra = divmod(RAIL_COUNT, n_robots)
    strips, start = [], 0
    for i in range(n_robots):
        size = base + (1 if i < extra else 0)
        strips.append(list(range(start, start + size)))
        start += size
    return strips


def work_rail(track: Track, index: int, start_depth: float, p: Params, rng: random.Random) -> None:
    """Đi vào hàng từ độ sâu start_depth, dừng mỗi k mét, tới cuối rồi lùi ra lối chính."""
    x, y_edge, direction = rail(index)
    # Điểm dừng kế tiếp là bội số của k tính từ đầu hàng.
    next_stop = (math.floor(start_depth / p.stop_every_m + EPS) + 1) * p.stop_every_m
    while next_stop <= RAIL_LENGTH + EPS:
        track.move_to(x, y_edge + direction * next_stop, p.rail_speed)
        track.wait(rng.uniform(p.stop_min_s, p.stop_max_s))
        next_stop += p.stop_every_m
        if track.t >= p.duration_s:
            return
    track.move_to(x, y_edge + direction * RAIL_LENGTH, p.rail_speed)
    track.move_to(x, y_edge, p.rail_speed)  # lùi ra, không dừng
    track.move_to(x, AISLE_Y, p.aisle_speed)


def robot_track(strip: list[int], p: Params, rng: random.Random) -> Track:
    pos_in_strip = rng.randrange(len(strip))
    start_depth = rng.uniform(0, RAIL_LENGTH)
    x, y_edge, direction = rail(strip[pos_in_strip])
    track = Track([(0.0, x, y_edge + direction * start_depth)])
    while True:
        work_rail(track, strip[pos_in_strip], start_depth, p, rng)
        if track.t >= p.duration_s:
            break
        pos_in_strip = (pos_in_strip + 1) % len(strip)
        x, y_edge, _ = rail(strip[pos_in_strip])
        track.move_to(x, AISLE_Y, p.aisle_speed)
        track.move_to(x, y_edge, p.aisle_speed)
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
    if in_aisle(y):
        return True
    k = round((x - RAIL_FIRST_X) / RAIL_SPACING)
    return 0 <= k < RAILS_PER_SIDE and abs(rail_x(k) - x) < EPS


def in_aisle(y: float) -> bool:
    return AISLE_Y_MIN - EPS <= y <= AISLE_Y_MAX + EPS


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
            if abs(x1 - x0) > EPS and not (in_aisle(y0) and in_aisle(y1)):
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
        "aisle": {"y_min": AISLE_Y_MIN, "y_max": AISLE_Y_MAX, "path_y": AISLE_Y},
        "rails": {
            "count": RAIL_COUNT,
            "per_side": RAILS_PER_SIDE,
            "first_x": RAIL_FIRST_X,
            "spacing_m": RAIL_SPACING,
            "length_m": RAIL_LENGTH,
            "north": {"y_start": AISLE_Y_MAX, "y_end": GREENHOUSE_Y},
            "south": {"y_start": AISLE_Y_MIN, "y_end": 0.0},
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
