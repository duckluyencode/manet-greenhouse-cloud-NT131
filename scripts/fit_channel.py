"""
Tham số kênh truyền log-distance cho NS-3 (mục 5) -> contracts/channel.json.

    PL(d) = PL(d0) + 10 n log10(d / d0) + X_sigma,   d0 = 1 m

- PL(d0) tính theo Friis ở tần số f (2,4 GHz -> 40,05 dB).
- n, sigma: fit bình phương tối thiểu trên số đo (biến độc lập 10·log10 d).
  Chỉ lấy độ dốc n từ phép fit; hệ số chặn lấy theo Friis (mục 5.3).
  sigma là độ lệch chuẩn phần dư của phép fit (bậc tự do m - 2).
- Tầm liên kết: d_max = d0 · 10^((P_tx - S_rx - PL(d0)) / (10 n)) (mục 5.4).

Radio mặc định: WiFi 802.11b 1 Mbps của robot, phát 20 dBm, độ nhạy -88 dBm (tầm ~29 m).
Robot dùng WiFi chứ không dùng radio 802.15.4 đã đo (mục 1.1, 5.4); cặp 16 / -82 dBm của
tài liệu cho tầm ~18 m, khi đó với 10 robot khoảng 80 % thời gian robot không có đường về
Gateway. Độ nhạy không được thấp hơn -90 dBm (nhiễu nền kênh 22 MHz + 4 dB): ns-3.48 dừng
với "Invalid WifiPhy state RX" ở ngưỡng sát nhiễu nền (xem simulation/scratch/caar.cc).

Số đo: CSV có cột distance_m, path_loss_db, nhập tay từ Bảng 2 của
Cama-Pinto et al. (2019). Repo chưa có file này; khi không truyền --measurements,
script dùng n, sigma đã ghi trong tài liệu đồ án (4,63 / 5,15 dB ở anten 0,5 m)
và ghi rõ nguồn trong channel.json.

Chạy: python scripts/fit_channel.py
      python scripts/fit_channel.py --tx-power 16 --rx-sensitivity -82   # cặp số của tài liệu
      python scripts/fit_channel.py --measurements data/cama_pinto_table2_0.5m.csv
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "contracts" / "channel.json"
SPEED_OF_LIGHT = 299_792_458.0
# Độ nhạy thấp nhất caar.cc chấp nhận (nhiễu nền 22 MHz + 4 dB SNR preamble).
MIN_RX_SENSITIVITY_DBM = -90.0

# Giá trị tài liệu đồ án đã fit từ Bảng 2 (mục 5.3), theo chiều cao anten.
DOCUMENTED_FIT = {
    0.5: {"n": 4.63, "sigma_db": 5.15},
    1.5: {"n": 5.23, "sigma_db": 1.39},
}


def friis_loss_db(freq_hz: float, dist_m: float = 1.0) -> float:
    """Suy hao không gian tự do 20·log10(4π d f / c)."""
    return 20 * math.log10(4 * math.pi * dist_m * freq_hz / SPEED_OF_LIGHT)


def fit_log_distance(distances_m: list[float], losses_db: list[float]) -> tuple[float, float]:
    """Hồi quy tuyến tính PL theo 10·log10 d; trả (n, sigma_db)."""
    if len(distances_m) < 3:
        raise ValueError("need at least 3 measurements")
    xs = [10 * math.log10(d) for d in distances_m]
    m = len(xs)
    mean_x = sum(xs) / m
    mean_y = sum(losses_db) / m
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, losses_db))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, losses_db)]
    sigma = math.sqrt(sum(r * r for r in residuals) / (m - 2))
    return slope, sigma


def link_range_m(tx_power_dbm: float, rx_sensitivity_dbm: float, ref_loss_db: float, n: float) -> float:
    budget = tx_power_dbm - rx_sensitivity_dbm
    return 10 ** ((budget - ref_loss_db) / (10 * n))


def read_measurements(path: Path) -> tuple[list[float], list[float]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [float(r["distance_m"]) for r in rows], [float(r["path_loss_db"]) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Tham số kênh log-distance cho NS-3 (mục 5)")
    parser.add_argument("--measurements", type=Path, help="CSV distance_m,path_loss_db")
    parser.add_argument("--antenna-height", type=float, default=0.5, choices=sorted(DOCUMENTED_FIT))
    parser.add_argument("--freq-ghz", type=float, default=2.4)
    parser.add_argument("--tx-power", type=float, default=20.0, help="dBm, công suất phát radio NS-3")
    parser.add_argument("--rx-sensitivity", type=float, default=-88.0, help="dBm, ngưỡng thu")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.rx_sensitivity < MIN_RX_SENSITIVITY_DBM:
        parser.error(f"--rx-sensitivity must be >= {MIN_RX_SENSITIVITY_DBM} dBm (noise floor + 4 dB)")

    ref_loss = friis_loss_db(args.freq_ghz * 1e9)
    if args.measurements:
        d, pl = read_measurements(args.measurements)
        n, sigma = fit_log_distance(d, pl)
        source = f"least-squares fit on {args.measurements.as_posix()} ({len(d)} points)"
    else:
        n = DOCUMENTED_FIT[args.antenna_height]["n"]
        sigma = DOCUMENTED_FIT[args.antenna_height]["sigma_db"]
        source = (
            "Cama-Pinto et al. 2019, Table 2 fit as recorded in the project document "
            "(section 5.3); re-fit with --measurements to verify"
        )

    rng = link_range_m(args.tx_power, args.rx_sensitivity, ref_loss, n)
    channel = {
        "n": round(n, 4),
        "sigma_db": round(sigma, 4),
        "ref_loss_db": round(ref_loss, 2),
        "ref_dist_m": 1.0,
        "freq_hz": args.freq_ghz * 1e9,
        "antenna_height_m": args.antenna_height,
        "tx_power_dbm": args.tx_power,
        "rx_sensitivity_dbm": args.rx_sensitivity,
        "link_range_m": round(rng, 2),
        "source": source,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(channel, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(channel, indent=2))


if __name__ == "__main__":
    main()
