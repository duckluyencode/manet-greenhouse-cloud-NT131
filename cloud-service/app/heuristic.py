"""
Heuristic chọn trọng số định tuyến toàn mạng (tài liệu đồ án, mục 7.2).

Đây là bản chuẩn (reference). Bản C++ trong simulation/caar-logic/caar_logic.h
phải cho kết quả giống hệt trên contracts/parity_cases.json.

Quy ước đã chốt 22/10/2026:
1. Robot yếu pin: energy_remaining_pct < 20 (đúng 20% không tính là yếu).
2. Đầu vào của trung vị RSSI: mỗi robot một giá trị rssi_avg.
3. Số robot chẵn: trung vị là trung bình hai giá trị giữa.
4. Luật đúng đầu tiên thắng: pin -> sóng -> cân bằng.
5. Tên luật: low_battery, poor_signal, balanced.
6. So sánh ngưỡng không chia cho 50 (tránh sai khác số thực giữa hai ngôn ngữ):
   - f_low >= 0.3  <=>  10 * số_robot_yếu >= 3 * số_robot
   - r_med < 0.3   <=>  2 * trung_vị(RSSI kẹp vào [-90; -40]) < -150
"""
from collections.abc import Iterable
from dataclasses import dataclass

LOW_BATTERY_PCT = 20.0
RSSI_MIN_DBM = -90.0
RSSI_MAX_DBM = -40.0
# 2 * trung vị RSSI (dBm) nhỏ hơn giá trị này <=> RSSI chuẩn hóa trung vị < 0.3.
POOR_SIGNAL_TWICE_MEDIAN_DBM = -150.0

RULE_LOW_BATTERY = "low_battery"
RULE_POOR_SIGNAL = "poor_signal"
RULE_BALANCED = "balanced"

# (hop_weight, rssi_weight, energy_weight) cho từng luật.
WEIGHT_TABLE: dict[str, tuple[float, float, float]] = {
    RULE_LOW_BATTERY: (0.2, 0.3, 0.5),
    RULE_POOR_SIGNAL: (0.3, 0.5, 0.2),
    RULE_BALANCED: (0.4, 0.3, 0.3),
}


@dataclass(frozen=True)
class NodeSample:
    """Phần telemetry của một robot mà heuristic cần."""

    rssi_avg: float
    energy_remaining_pct: float


@dataclass(frozen=True)
class Decision:
    rule: str
    hop_weight: float
    rssi_weight: float
    energy_weight: float


def clamp_rssi(rssi_dbm: float) -> float:
    """Kẹp RSSI vào [-90; -40] dBm."""
    return min(RSSI_MAX_DBM, max(RSSI_MIN_DBM, rssi_dbm))


def twice_median(values: list[float]) -> float:
    """Trả về 2 × trung vị, để số chẵn phần tử không phải chia cho 2."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return 2.0 * ordered[mid]
    return ordered[mid - 1] + ordered[mid]


def select_rule(nodes: Iterable[NodeSample]) -> str:
    """Chọn luật theo thứ tự pin -> sóng -> cân bằng. Danh sách rỗng -> balanced."""
    nodes = list(nodes)
    if not nodes:
        return RULE_BALANCED

    weak = sum(1 for n in nodes if n.energy_remaining_pct < LOW_BATTERY_PCT)
    if 10 * weak >= 3 * len(nodes):
        return RULE_LOW_BATTERY

    rssi = [clamp_rssi(n.rssi_avg) for n in nodes]
    if twice_median(rssi) < POOR_SIGNAL_TWICE_MEDIAN_DBM:
        return RULE_POOR_SIGNAL

    return RULE_BALANCED


def choose_weights(nodes: Iterable[NodeSample]) -> Decision:
    """Hàm thuần: telemetry toàn mạng -> luật và bộ trọng số (w_h, w_r, w_e)."""
    rule = select_rule(nodes)
    wh, wr, we = WEIGHT_TABLE[rule]
    return Decision(rule=rule, hop_weight=wh, rssi_weight=wr, energy_weight=we)


def normalize_rssi(rssi_dbm: float) -> float:
    """r_i = min(1, max(0, (RSSI + 90) / 50)) (mục 4.1)."""
    return min(1.0, max(0.0, (rssi_dbm + 90.0) / 50.0))


def node_cost(
    hop_weight: float,
    rssi_weight: float,
    energy_weight: float,
    rssi_dbm: float,
    energy_frac: float,
) -> float:
    """c_i = w_h + w_r (1 - r_i) + w_e (1 - e_i) (mục 4.1).

    Bản tham chiếu cho caar_logic.h; cloud không dùng hàm này khi chạy.
    """
    r = normalize_rssi(rssi_dbm)
    e = min(1.0, max(0.0, energy_frac))
    return hop_weight + rssi_weight * (1.0 - r) + energy_weight * (1.0 - e)
