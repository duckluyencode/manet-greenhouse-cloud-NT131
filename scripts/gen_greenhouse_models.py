"""
Sinh mô hình 3D nhà kính cho trình xem NetSimulyzer (OBJ + MTL, đơn vị mét, trục Y hướng lên).

Kích thước lấy từ contracts/waypoints/layout.json để khớp với quỹ đạo robot:
- frame.obj      khung thép kiểu Venlo: cột, máng xối, đỉnh mái, kèo, giằng ngang, giằng tường,
                 khung cửa ở hai đầu lối đi giữa
- glass.obj      kính mái và vách (trong suốt một phần), chừa cửa ở hai đầu lối đi
- plant_row.obj  một hàng cà chua treo dây: máng giá thể, thân, tán lá, quả; caar.cc đặt một bản
                 giữa mỗi cặp ray ở cả hai phía lối đi

frame.obj và glass.obj dùng tọa độ ns-3 tuyệt đối (đặt ở gốc). NetSimulyzer đổi tọa độ ns-3
(x, y, z) sang OpenGL (x, z, -y), nên đỉnh OBJ ghi (x, z, -y). plant_row.obj có tâm ở gốc, hàng
chạy dọc trục y của ns-3.

Không dùng biến ngẫu nhiên: độ lệch lá, quả thay đổi theo chỉ số cây (hàm băm cố định), nên chạy
lại cho cùng file.

Chạy: python scripts/gen_greenhouse_models.py      # ghi vào simulation/netsimulyzer/models/caar/
Cài vào trình xem: chép thư mục caar/ vào <thư mục trình xem>/resources/models/
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "contracts" / "waypoints" / "layout.json"
OUT = ROOT / "simulation" / "netsimulyzer" / "models" / "caar"

GUTTER_H = 4.5  # chiều cao máng xối (m)
RIDGE_H = 5.6  # chiều cao đỉnh mái
TRUSS_STEP = 5.0  # khoảng cách kèo dọc theo y
PLANT_STEP = 0.5  # khoảng cách cây trong hàng
PLANT_H = 2.3  # chiều cao cây cà chua

Vec = tuple[float, float, float]


class Mesh:
    """Lưới tam giác/tứ giác theo nhóm vật liệu, tọa độ ns-3 (z hướng lên)."""

    def __init__(self) -> None:
        self.verts: list[Vec] = []
        self.normals: list[Vec] = []
        self.normal_idx: dict[Vec, int] = {}
        self.groups: dict[str, list[tuple[list[int], int]]] = {}

    def _normal(self, n: Vec) -> int:
        key = tuple(round(c, 4) for c in n)
        if key not in self.normal_idx:
            self.normals.append(key)
            self.normal_idx[key] = len(self.normals)
        return self.normal_idx[key]

    def face(self, material: str, pts: list[Vec], outward: Vec | None = None) -> None:
        """Thêm một mặt; nếu cho outward (điểm tâm khối) thì lật để pháp tuyến hướng ra ngoài."""
        n = _unit(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        if outward is not None:
            center = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
            if _dot(n, _sub(center, outward)) < 0:
                pts = pts[::-1]
                n = (-n[0], -n[1], -n[2])
        base = len(self.verts)
        self.verts.extend(pts)
        self.groups.setdefault(material, []).append(
            ([base + i + 1 for i in range(len(pts))], self._normal(n)))

    def two_sided(self, material: str, pts: list[Vec]) -> None:
        self.face(material, pts)
        self.face(material, pts[::-1])

    def box(self, material: str, lo: Vec, hi: Vec) -> None:
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        self._hexahedron(material, corners, c)

    def beam(self, material: str, a: Vec, b: Vec, w: float, h: float | None = None) -> None:
        """Thanh tiết diện chữ nhật w × h từ a tới b (cho kèo xiên)."""
        h = w if h is None else h
        d = _unit(_sub(b, a))
        up = (0.0, 0.0, 1.0) if abs(d[2]) < 0.95 else (1.0, 0.0, 0.0)
        s = _unit(_cross(d, up))
        u = _cross(s, d)
        corners = []
        for end in (a, b):
            for i in (-1, 1):
                for j in (-1, 1):
                    corners.append(tuple(end[k] + i * w / 2 * s[k] + j * h / 2 * u[k] for k in range(3)))
        c = tuple((a[k] + b[k]) / 2 for k in range(3))
        # đổi thứ tự cho giống box(): chỉ số bit (x, y, z) -> (end, i, j)
        self._hexahedron(material, corners, c)

    def _hexahedron(self, material: str, c: list[Vec], center: Vec) -> None:
        # c theo thứ tự bit (a, b, c) với a là bit cao: 0..7
        for quad in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
            self.face(material, [c[i] for i in quad], center)

    def octahedron(self, material: str, center: Vec, rx: float, ry: float, rz: float) -> None:
        x, y, z = center
        px, nx = (x + rx, y, z), (x - rx, y, z)
        py, ny = (x, y + ry, z), (x, y - ry, z)
        pz, nz = (x, y, z + rz), (x, y, z - rz)
        for a, b in ((px, py), (py, nx), (nx, ny), (ny, px)):
            self.face(material, [a, b, pz], center)
            self.face(material, [a, b, nz], center)

    def write(self, path: Path, materials: dict[str, tuple[tuple[float, float, float], float]]) -> None:
        mtl = path.with_suffix(".mtl")
        lines = [f"newmtl {name}\nNs 60\nKa 1 1 1\nKd {r:.3f} {g:.3f} {b:.3f}\nKs 0.2 0.2 0.2\n"
                 f"Ke 0 0 0\nNi 1.45\nd {alpha:.2f}\nillum 2\n"
                 for name, ((r, g, b), alpha) in materials.items() if name in self.groups]
        mtl.write_text("# CAAR greenhouse, scripts/gen_greenhouse_models.py\n" + "\n".join(lines),
                       encoding="utf-8", newline="\n")
        out = [f"# CAAR greenhouse, scripts/gen_greenhouse_models.py\nmtllib {mtl.name}\no {path.stem}"]
        # ns-3 (x, y, z) -> OpenGL (x, z, -y)
        out += [f"v {x:.3f} {z:.3f} {-y:.3f}" for x, y, z in self.verts]
        out += [f"vn {x:.4f} {z:.4f} {-y:.4f}" for x, y, z in self.normals]
        for name, faces in self.groups.items():
            out.append(f"usemtl {name}")
            out += ["f " + " ".join(f"{i}//{n}" for i in idx) for idx, n in faces]
        path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
        print(f"{path}: {len(self.verts)} vertices, "
              f"{sum(len(f) for f in self.groups.values())} faces")


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec) -> Vec:
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _hash01(*keys: int) -> float:
    """Số giả ngẫu nhiên cố định trong [0, 1) từ các chỉ số (không dùng bộ sinh ngẫu nhiên)."""
    h = 2166136261
    for k in keys:
        h = ((h ^ (k & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return h / 2**32


def gutter_lines(width: float, first_x: float, spacing: float, per_side: int) -> list[float]:
    """Đường máng xối (hàng cột): hai vách và cứ 5 ray (~9 m) một đường bên trong, đặt giữa ray
    và hàng cây; số đường theo số ray mỗi bên nên nhà kính rộng hơn vẫn có cột khắp nơi."""
    inner = [first_x + spacing * k - spacing / 4 for k in range(5, per_side, 5)]
    return [0.0, *[x for x in inner if 1 < x < width - 1], width]


def build_frame(layout: dict) -> tuple[Mesh, Mesh]:
    width, depth = layout["greenhouse_m"]
    aisle_min, aisle_max = layout["aisle"]["y_min"], layout["aisle"]["y_max"]
    rails = layout["rails"]
    xs = gutter_lines(width, rails["first_x"], rails["spacing_m"], rails["per_side"])
    ys = [i * TRUSS_STEP for i in range(int(depth / TRUSS_STEP) + 1)]
    frame, glass = Mesh(), Mesh()
    steel, light = "steel", "steel_light"

    # cột (trừ trong lối đi giữa) và giằng tường
    for x in xs:
        for y in ys:
            if aisle_min < y < aisle_max:
                continue
            frame.box(steel, (x - 0.07, y - 0.07, 0), (x + 0.07, y + 0.07, GUTTER_H))
    # máng xối dọc mỗi hàng cột
    for x in xs:
        frame.box(steel, (x - 0.12, 0, GUTTER_H), (x + 0.12, depth, GUTTER_H + 0.18))
    for x0, x1 in zip(xs, xs[1:]):
        xc = (x0 + x1) / 2
        frame.box(light, (xc - 0.05, 0, RIDGE_H - 0.05), (xc + 0.05, depth, RIDGE_H + 0.05))  # đỉnh mái
        for y in ys:
            frame.beam(light, (x0, y, GUTTER_H + 0.18), (xc, y, RIDGE_H), 0.06)  # kèo
            frame.beam(light, (x1, y, GUTTER_H + 0.18), (xc, y, RIDGE_H), 0.06)
            frame.box(light, (x0, y - 0.03, GUTTER_H - 0.25), (x1, y + 0.03, GUTTER_H - 0.19))  # giằng
        # xà gồ giữa máng và đỉnh, hai bên
        for side in (x0, x1):
            mx = (side + xc) / 2
            mz = (GUTTER_H + 0.18 + RIDGE_H) / 2
            frame.box(light, (mx - 0.03, 0, mz - 0.03), (mx + 0.03, depth, mz + 0.03))
        # kính mái
        for side in (x0, x1):
            glass.two_sided("glass", [(side, 0, GUTTER_H + 0.18), (side, depth, GUTTER_H + 0.18),
                                      (xc, depth, RIDGE_H), (xc, 0, RIDGE_H)])
        # kính hồi (tam giác hai đầu)
        for y in (0.0, depth):
            glass.two_sided("glass", [(x0, y, GUTTER_H + 0.18), (x1, y, GUTTER_H + 0.18), (xc, y, RIDGE_H)])

    # giằng ngang trên vách bốn phía và chân tường
    for z in (0.0, 1.5, 3.0):
        for x in (0.0, width):
            for y0, y1 in ((0, aisle_min), (aisle_max, depth)) if z < 2.6 else ((0, depth),):
                frame.box(steel, (x - 0.05, y0, z), (x + 0.05, y1, z + 0.1))
        for y in (0.0, depth):
            frame.box(steel, (0, y - 0.05, z), (width, y + 0.05, z + 0.1))
    # khung cửa hai đầu lối đi giữa
    for x in (0.0, width):
        for y in (aisle_min, aisle_max):
            frame.box(steel, (x - 0.09, y - 0.09, 0), (x + 0.09, y + 0.09, 3.0))
        frame.box(steel, (x - 0.09, aisle_min, 3.0), (x + 0.09, aisle_max, 3.18))

    # kính vách, chừa cửa
    for x in (0.0, width):
        for y0, y1 in ((0, aisle_min), (aisle_max, depth)):
            glass.two_sided("glass", [(x, y0, 0), (x, y1, 0), (x, y1, GUTTER_H), (x, y0, GUTTER_H)])
        glass.two_sided("glass", [(x, aisle_min, 3.18), (x, aisle_max, 3.18),
                                  (x, aisle_max, GUTTER_H), (x, aisle_min, GUTTER_H)])
    for y in (0.0, depth):
        glass.two_sided("glass", [(0, y, 0), (width, y, 0), (width, y, GUTTER_H), (0, y, GUTTER_H)])
    return frame, glass


def build_plant_row(length: float) -> Mesh:
    """Một hàng cà chua dài `length` dọc trục y, tâm ở gốc."""
    m = Mesh()
    half = length / 2
    m.box("substrate", (-0.17, -half, 0.0), (0.17, half, 0.16))  # máng giá thể
    count = int(length / PLANT_STEP)
    for i in range(count):
        y = -half + PLANT_STEP * (i + 0.5)
        lean = (_hash01(i, 1) - 0.5) * 0.12
        top = PLANT_H * (0.9 + 0.1 * _hash01(i, 2))
        m.beam("stem", (0.0, y, 0.16), (lean, y, top), 0.035)
        for level, z in enumerate((0.7, 1.05, 1.4, 1.75, 2.05)):
            if z > top:
                break
            side = 1 if (i + level) % 2 else -1
            dx = side * (0.18 + 0.08 * _hash01(i, level, 3))
            leaf = "leaf_dark" if level % 2 else "leaf"
            m.octahedron(leaf, (lean * z / top + dx, y, z), 0.24, 0.2, 0.09)
        m.octahedron("leaf", (lean, y, top), 0.16, 0.16, 0.12)  # ngọn
        for t in range(2):
            if _hash01(i, t, 7) < 0.55:
                fz = 0.55 + 0.35 * _hash01(i, t, 8)
                fx = (0.09 if t else -0.09) + lean * fz / top
                ripe = "fruit" if _hash01(i, t, 9) < 0.6 else "fruit_green"
                m.octahedron(ripe, (fx, y + 0.06, fz), 0.055, 0.055, 0.055)
    return m


MATERIALS = {
    "steel": ((0.55, 0.57, 0.60), 1.0),
    "steel_light": ((0.78, 0.80, 0.82), 1.0),
    "glass": ((0.80, 0.90, 0.96), 0.18),
    "substrate": ((0.92, 0.92, 0.90), 1.0),
    "stem": ((0.30, 0.45, 0.18), 1.0),
    "leaf": ((0.25, 0.60, 0.20), 1.0),
    "leaf_dark": ((0.13, 0.42, 0.13), 1.0),
    "fruit": ((0.85, 0.12, 0.08), 1.0),
    "fruit_green": ((0.55, 0.75, 0.25), 1.0),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh mô hình 3D nhà kính cho NetSimulyzer")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    frame, glass = build_frame(layout)
    frame.write(args.out / "frame.obj", MATERIALS)
    glass.write(args.out / "glass.obj", MATERIALS)
    build_plant_row(layout["rails"]["length_m"] - 1.0).write(args.out / "plant_row.obj", MATERIALS)


if __name__ == "__main__":
    main()
