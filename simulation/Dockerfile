# Môi trường NS-3 dùng chung cho cả nhóm (mục 13.1, 13.5): Ubuntu 24.04 + ns-3.48.
#
# Build từ gốc repo (context phải là repo vì cần contracts/ và simulation/):
#   docker build -f simulation/Dockerfile -t caar-ns3 .
# Chạy một kịch bản:
#   docker run --rm -v "$PWD:/repo" caar-ns3 \
#     /opt/ns-3-dev/ns3 run --no-build "caar --config=no_cloud --seed=1 --nodes=10 \
#       --waypoints=/repo/contracts/waypoints/10_1.csv --channel=/repo/contracts/channel.json \
#       --out=/repo/results/raw/no_cloud_baseline_1.csv"
# Chạy hàng loạt:
#   docker run --rm -v "$PWD:/repo" -e NS3_DIR=/opt/ns-3-dev caar-ns3 /repo/scripts/run_batch.sh s1
# Demo kèm cảnh 3D (ghi results/demo/<tên>.json, mở bằng NetSimulyzer trên máy thật):
#   docker run --rm -v "$PWD:/repo" -e NS3_DIR=/opt/ns-3-dev caar-ns3 \
#     bash /repo/simulation/vm/demo.sh cloud_assisted outage 1 10
# Không cần cảnh 3D: docker build --build-arg NETSIMULYZER=0 ...

# --- base: ns-3.48 gốc, chỉ các module CAAR cần ---------------------------------
FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ cmake ninja-build python3 git ca-certificates ccache patch \
    && rm -rf /var/lib/apt/lists/*

ARG NS3_TAG=ns-3.48
ARG NETSIMULYZER=1
WORKDIR /opt
RUN git clone --depth 1 --branch ${NS3_TAG} https://gitlab.com/nsnam/ns-3-dev.git ns-3-dev \
    && if [ "$NETSIMULYZER" = 1 ]; then \
         git clone --depth 1 --branch v1.0.17 https://github.com/usnistgov/NetSimulyzer-ns3-module.git \
           ns-3-dev/contrib/netsimulyzer; \
       fi

# Profile release = optimized nhưng không có -march=native: file chạy dùng được trên mọi CPU
# x86-64 và cùng seed cho cùng kết quả trên mọi máy.
# Mỗi luồng biên dịch module wifi cần ~1 GB RAM; tăng JOBS nếu Docker có nhiều RAM hơn.
ARG JOBS=4
ENV JOBS=${JOBS}
WORKDIR /opt/ns-3-dev
RUN MODULES="aodv;wifi;mobility;internet;applications;flow-monitor;propagation;netanim" \
    && if [ "$NETSIMULYZER" = 1 ]; then MODULES="$MODULES;netsimulyzer"; fi \
    && ./ns3 configure --build-profile=release --disable-examples --disable-tests --enable-modules="$MODULES" \
    && ./ns3 build -j ${JOBS}

# --- caar: áp patch delayed RREQ + kịch bản scratch/caar --------------------------
FROM base AS caar

COPY simulation/aodv-patch /tmp/caar/simulation/aodv-patch
COPY simulation/scratch /tmp/caar/simulation/scratch
COPY simulation/caar-logic /tmp/caar/simulation/caar-logic
COPY simulation/install.sh /tmp/caar/simulation/install.sh
RUN /tmp/caar/simulation/install.sh /opt/ns-3-dev && ./ns3 build -j ${JOBS}

WORKDIR /repo
CMD ["/bin/bash"]
