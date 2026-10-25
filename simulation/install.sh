#!/usr/bin/env bash
# Cài CAAR vào một bản ns-3-dev (tag ns-3.48):
#   1. áp patch delayed RREQ forwarding vào src/aodv (bỏ qua nếu đã áp),
#   2. chép kịch bản và caar_logic.h vào scratch/caar/.
# Sau đó: cd <ns-3-dev> && ./ns3 build && ./ns3 run "caar --help"
#
#   simulation/install.sh ~/ns-3-dev
set -euo pipefail

NS3_DIR="${1:?usage: install.sh <ns-3-dev dir>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH="$HERE/aodv-patch/caar-delayed-rreq.patch"

cd "$NS3_DIR"
if patch -p1 --dry-run --reverse --force --silent < "$PATCH" > /dev/null 2>&1; then
  echo "AODV patch already applied"
else
  patch -p1 --forward < "$PATCH"
  echo "AODV patch applied"
fi

mkdir -p scratch/caar
cp "$HERE/scratch/caar.cc" scratch/caar/caar.cc
cp "$HERE/caar-logic/caar_logic.h" scratch/caar/caar_logic.h
echo "scratch/caar installed; build with: ./ns3 build"
