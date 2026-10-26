#!/usr/bin/env bash
# Chạy một kịch bản CAAR trên ns-3 đã cài bằng setup-ubuntu.sh, in kết quả ra terminal,
# ghi trace NetAnim rồi mở NetAnim để xem.
#
#   bash simulation/vm/demo.sh                          # cloud_assisted, mất cloud 300–600 s
#   bash simulation/vm/demo.sh no_cloud baseline        # AODV gốc
#   bash simulation/vm/demo.sh local_optimized baseline 3 20   # seed 3, 20 robot
#
# Tham số: [config] [scenario] [seed] [số robot]
#   config:   no_cloud | local_optimized | gateway_heuristic | cloud_assisted
#   scenario: baseline | outage (mất cloud 300–600 s, chỉ có tác dụng với cloud_assisted)
# Cửa sổ ghi gói tin cho NetAnim: NETANIM_START / NETANIM_STOP (mặc định 290–320 s).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-3-dev}"
NETANIM_DIR="${NETANIM_DIR:-$HOME/netanim}"
CONFIG="${1:-cloud_assisted}"
SCENARIO="${2:-outage}"
SEED="${3:-1}"
NODES="${4:-10}"
START="${NETANIM_START:-290}"
STOP="${NETANIM_STOP:-320}"

[[ -x "$NS3_DIR/ns3" ]] || { echo "Chưa có ns-3 ở $NS3_DIR, chạy simulation/vm/setup-ubuntu.sh trước" >&2; exit 1; }
WAYPOINTS="$REPO/contracts/waypoints/${NODES}_${SEED}.csv"
[[ -f "$WAYPOINTS" ]] || { echo "Không có quỹ đạo $WAYPOINTS (số robot 6/10/16/20, seed 1–10)" >&2; exit 1; }

OUT_DIR="$REPO/results/demo"
mkdir -p "$OUT_DIR"
NAME="${CONFIG}_${SCENARIO}_n${NODES}_s${SEED}"
EXTRA=""
[[ "$SCENARIO" == "outage" ]] && EXTRA="--outage-start=300 --outage-end=600"

echo "Kịch bản: $CONFIG / $SCENARIO, $NODES robot, seed $SEED (900 s mô phỏng)"
cd "$NS3_DIR"
./ns3 run "caar --config=$CONFIG --scenario=$SCENARIO --seed=$SEED --nodes=$NODES \
  --waypoints=$WAYPOINTS --channel=$REPO/contracts/channel.json --ttl=60 --dmax=20 $EXTRA \
  --out=$OUT_DIR/$NAME.csv --netanim=$OUT_DIR/$NAME.xml --netanim-start=$START --netanim-stop=$STOP"

echo
echo "Kết quả (CSV):   $OUT_DIR/$NAME.csv"
[[ -f "$OUT_DIR/${NAME}_events.csv" ]] && echo "Log Gateway:     $OUT_DIR/${NAME}_events.csv"
echo "Trace NetAnim:   $OUT_DIR/$NAME.xml"
echo "Trong NetAnim: File > Open > chọn file .xml ở trên, rồi bấm nút Play (▶)."
echo "  Robot: xanh lá = pin đầy, đỏ = pin yếu. Gateway: xanh dương L1, cam L2, đỏ L3 (mất cloud)."
echo "  Gói tin chỉ được vẽ trong khoảng ${START}–${STOP} s; kéo thanh thời gian tới đó."

if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" && -x "$NETANIM_DIR/NetAnim" ]]; then
  ("$NETANIM_DIR/NetAnim" >/dev/null 2>&1 &)
  echo "Đã mở NetAnim."
else
  echo "Không có màn hình đồ hoạ hoặc chưa build NetAnim: mở $NETANIM_DIR/NetAnim bằng tay."
fi
