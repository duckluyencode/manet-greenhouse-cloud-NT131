# NS-3 3.42 build environment
# Ubuntu 22.04 + cmake 3.25+ + g++ 11 + Python 3.10
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Cài dependencies
RUN apt-get update && apt-get install -y \
    g++ \
    python3 \
    python3-dev \
    python3-pip \
    cmake \
    ninja-build \
    git \
    ccache \
    libboost-all-dev \
    libgsl-dev \
    libsqlite3-dev \
    libxml2-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. Nâng cmake lên 3.25+
RUN apt-get update && apt-get install -y software-properties-common \
    && wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc | apt-key add - \
    && apt-add-repository 'deb https://apt.kitware.com/ubuntu/ jammy main' \
    && apt-get update && apt-get install -y cmake \
    && rm -rf /var/lib/apt/lists/*

# 3. Clone NS-3
WORKDIR /opt
RUN git clone https://gitlab.com/nsnam/ns-3-dev.git ns-3-dev

# 4. Build NS-3
WORKDIR /opt/ns-3-dev
RUN ./ns3 configure --enable-tests --enable-examples \
    && ./ns3 build -j4

# 5. Thư mục làm việc
WORKDIR /opt/ns-3-dev/scratch

CMD ["/bin/bash"]