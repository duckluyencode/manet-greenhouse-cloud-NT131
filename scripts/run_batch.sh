#!/usr/bin/env bash
# Chạy hàng loạt config × seed × tham số cho các kịch bản mục 10.2.
#
#   NS3_DIR=~/ns-3-dev scripts/run_batch.sh s1 s2a s2b      # tối thiểu để bảo vệ
#   NS3_DIR=~/ns-3-dev scripts/run_batch.sh all
#   scripts/run_batch.sh --dry-run all                       # chỉ in lệnh
#
# Kịch bản: s1 (baseline), s2a (outage), s2b (stale), s3 (scale), sens (sensitivity), all.
# Mỗi run ghi results/raw/<config>_<scenario>[_<biến thể>]_<seed>.csv; run đã có file thì bỏ qua,
# nên chạy lại sau khi bị ngắt sẽ tiếp tục từ chỗ dừng.
#
# Tham số dòng lệnh truyền cho scratch/caar (Owner A cài đặt):
#   --config --seed --nodes --dmax --ttl --outage-start --outage-end --wan-trace  (mục 13.5)
#   --scenario --waypoints --channel --out                                         (thêm, xem contracts/README.md)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="${RAW:-$REPO/results/raw}"
CONTRACTS="$REPO/contracts"
SEEDS="${SEEDS:-1 2 3 4 5 6 7 8 9 10}"
CONFIGS="no_cloud local_optimized gateway_heuristic cloud_assisted"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi
if [[ $# -eq 0 ]]; then
  sed -n '2,13p' "$0"
  exit 1
fi
if [[ $DRY_RUN -eq 0 && -z "${NS3_DIR:-}" ]]; then
  echo "set NS3_DIR to the ns-3-dev checkout (or use --dry-run)" >&2
  exit 1
fi
mkdir -p "$RAW"

total=0
skipped=0
failed=0

# run <config> <scenario> <variant> <seed> <nodes> <waypoint-tag> [extra args...]
run() {
  local config=$1 scenario=$2 variant=$3 seed=$4 nodes=$5 wp_tag=$6
  shift 6
  local name="${config}_${scenario}"
  [[ -n "$variant" ]] && name+="_${variant}"
  local out="$RAW/${name}_${seed}.csv"
  local waypoints="$CONTRACTS/waypoints/${nodes}_${seed}${wp_tag:+_$wp_tag}.csv"
  local args="scratch/caar --config=$config --scenario=$scenario --seed=$seed --nodes=$nodes"
  args+=" --waypoints=$waypoints --channel=$CONTRACTS/channel.json --out=$out"
  if [[ "$config" == "cloud_assisted" ]]; then
    args+=" --wan-trace=$CONTRACTS/wan_trace.csv"
  fi
  [[ $# -gt 0 ]] && args+=" $*"

  total=$((total + 1))
  if [[ -s "$out" ]]; then
    skipped=$((skipped + 1))
    return
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "./ns3 run \"$args\""
    return
  fi
  echo "[$total] $name seed=$seed"
  if ! (cd "$NS3_DIR" && ./ns3 run --no-build "$args" > "$RAW/${name}_${seed}.log" 2>&1); then
    echo "  FAILED, see $RAW/${name}_${seed}.log" >&2
    failed=$((failed + 1))
  fi
}

s1() {  # Hiệu năng: 4 cấu hình, tham số mặc định — Q1, Q2a, Q2b
  for seed in $SEEDS; do
    for config in $CONFIGS; do
      run "$config" baseline "" "$seed" 10 "" --ttl=60 --dmax=20
    done
  done
}

s2a() {  # Mất cloud 300–600 s — Q3
  for seed in $SEEDS; do
    run cloud_assisted outage "" "$seed" 10 "" --ttl=60 --dmax=20 --outage-start=300 --outage-end=600
  done
}

s2b() {  # Trọng số cũ: TTL 15, 60, 300 s
  for seed in $SEEDS; do
    for ttl in 15 60 300; do
      run cloud_assisted stale "ttl$ttl" "$seed" 10 "" --ttl="$ttl" --dmax=20 --outage-start=300 --outage-end=600
    done
  done
}

s3() {  # Quy mô: 6, 10, 16, 20 robot
  for seed in $SEEDS; do
    for nodes in 6 10 16 20; do
      for config in $CONFIGS; do
        run "$config" scale "n$nodes" "$seed" "$nodes" "" --ttl=60 --dmax=20
      done
    done
  done
}

sens() {  # Độ nhạy: D_max 5, 10, 20 ms; tốc độ 0,2 và 1 m/s
  for seed in $SEEDS; do
    for config in local_optimized cloud_assisted; do
      for dmax in 5 10 20; do
        run "$config" sensitivity "dmax$dmax" "$seed" 10 "" --ttl=60 --dmax="$dmax"
      done
      # Tốc độ 0,2 m/s chính là run dmax20 ở trên nên không chạy lại.
      # Quỹ đạo 1 m/s: python scripts/gen_waypoints.py --nodes 10 --rail-speed 1 --aisle-speed 1 --tag v1
      run "$config" sensitivity "speedv1" "$seed" 10 v1 --ttl=60 --dmax=20
    done
  done
}

for target in "$@"; do
  case "$target" in
    s1|s2a|s2b|s3|sens) "$target" ;;
    all) s1; s2a; s2b; s3; sens ;;
    *) echo "unknown scenario: $target" >&2; exit 1 ;;
  esac
done

echo "runs: $total total, $skipped already done, $failed failed" >&2
[[ $failed -eq 0 ]]
