#!/usr/bin/env bash
# Cài CAAR trên Ubuntu 24.04 (máy thật hoặc máy ảo có giao diện), không dùng Docker:
#   1. gói hệ thống (g++, CMake, Qt5...)
#   2. ns-3.48 vào ~/ns-3-dev
#   3. patch AODV delayed RREQ + kịch bản scratch/caar (simulation/install.sh)
#   4. build ns-3 (profile release)
#   5. trình xem NetAnim 3.109 vào ~/netanim, kèm netanim-wpr.patch để vẽ được gói wifi
#
# Chạy từ thư mục repo:   bash simulation/vm/setup-ubuntu.sh
# Đổi nơi cài:            NS3_DIR=~/ns3 NETANIM_DIR=~/na bash simulation/vm/setup-ubuntu.sh
# Chạy lại an toàn: bước nào đã xong thì bỏ qua.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-3-dev}"
NETANIM_DIR="${NETANIM_DIR:-$HOME/netanim}"
NS3_TAG=ns-3.48
NETANIM_TAG=netanim-3.109
MODULES="aodv;wifi;mobility;internet;applications;flow-monitor;propagation;netanim"
SUDO=""
[[ "$(id -u)" -ne 0 ]] && SUDO=sudo

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

# Mỗi luồng biên dịch module wifi cần ~1,5 GB RAM; máy ảo ít RAM thì build ít luồng hơn.
mem_gb=$(awk '/MemTotal/ {printf "%d", $2 / 1024 / 1024}' /proc/meminfo)
JOBS="${JOBS:-$(( mem_gb * 2 / 3 ))}"
(( JOBS < 1 )) && JOBS=1
(( JOBS > $(nproc) )) && JOBS=$(nproc)

step "1/5 Cài gói hệ thống"
# libqt5svg5: biểu tượng trên thanh công cụ NetAnim là ảnh SVG.
PACKAGES="g++ cmake ninja-build python3 git patch ccache make qtbase5-dev qt5-qmake libqt5svg5"
if dpkg -s $PACKAGES >/dev/null 2>&1; then
  echo "đã có, bỏ qua"
else
  $SUDO apt-get update
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $PACKAGES
fi
echo "g++   $(g++ -dumpfullversion)   (cần >= 11)"
echo "cmake $(cmake --version | head -1 | awk '{print $3}')   (cần >= 3.25)"
echo "RAM ${mem_gb} GB, CPU $(nproc) -> build ${JOBS} luồng song song"

step "2/5 Tải ns-3 ($NS3_TAG) vào $NS3_DIR"
if [[ -d "$NS3_DIR/.git" ]]; then
  echo "đã có, bỏ qua"
else
  git clone --depth 1 --branch "$NS3_TAG" https://gitlab.com/nsnam/ns-3-dev.git "$NS3_DIR"
fi

step "3/5 Áp patch CAAR và chép kịch bản scratch/caar"
bash "$REPO/simulation/install.sh" "$NS3_DIR"

step "4/5 Build ns-3 (lần đầu mất 20–60 phút tùy máy)"
cd "$NS3_DIR"
./ns3 configure --build-profile=release --disable-examples --disable-tests --enable-modules="$MODULES"
./ns3 build -j "$JOBS"

step "5/5 Build trình xem NetAnim ($NETANIM_TAG) vào $NETANIM_DIR"
[[ -d "$NETANIM_DIR" ]] || git clone --depth 1 --branch "$NETANIM_TAG" https://gitlab.com/nsnam/netanim.git "$NETANIM_DIR"
# NetAnim 3.109 đọc bản ghi gói wifi <pr> + <wpr> của ns-3 nhưng không vẽ; patch cho nó vẽ.
if grep -q "CAAR:" "$NETANIM_DIR/animxmlparser.cpp"; then
  echo "patch gói wifi đã áp"
else
  patch -d "$NETANIM_DIR" -p1 < "$REPO/simulation/vm/netanim-wpr.patch"
  rm -f "$NETANIM_DIR/NetAnim"
fi
if [[ -x "$NETANIM_DIR/NetAnim" ]]; then
  echo "đã có, bỏ qua"
else
  (cd "$NETANIM_DIR" && qmake NetAnim.pro && make -j "$(nproc)")
fi

step "Xong"
echo "ns-3:    $NS3_DIR   (thử: cd $NS3_DIR && ./ns3 run \"caar --help\")"
echo "NetAnim: $NETANIM_DIR/NetAnim"
echo "Chạy mô phỏng và xem bằng NetAnim:  bash simulation/vm/demo.sh"
