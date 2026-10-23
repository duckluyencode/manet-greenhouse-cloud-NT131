# simulation/ — NS-3 (ns-3.48)

| Thư mục / file | Nội dung |
|---|---|
| `aodv-patch/caar-delayed-rreq.patch` | Patch `src/aodv`: hook thời gian chờ rebroadcast RREQ + trace `RouteDiscovery` |
| `scratch/caar.cc` | Kịch bản 4 cấu hình (mục 10.1), đọc `contracts/`, ghi CSV kết quả |
| `caar-logic/caar_logic.h` | Heuristic, chi phí c_i, máy trạng thái Gateway (C++ thuần, có parity test) |
| `install.sh` | Áp patch (bỏ qua nếu đã áp) và chép `caar.cc` + `caar_logic.h` vào `scratch/caar/` |
| `Dockerfile` | Ubuntu 24.04 + ns-3.48 đã cài CAAR |

## Cài trên máy (Ubuntu 24.04 / WSL2)

```bash
sudo apt install g++ cmake ninja-build python3 git patch ccache
git clone --depth 1 --branch ns-3.48 https://gitlab.com/nsnam/ns-3-dev.git ~/ns-3-dev
simulation/install.sh ~/ns-3-dev
cd ~/ns-3-dev
./ns3 configure --build-profile=optimized --disable-examples --disable-tests \
  --enable-modules="aodv;wifi;mobility;internet;applications;flow-monitor;propagation;netanim"
./ns3 build
```

Sửa `caar.cc` hoặc `caar_logic.h` trong repo thì chạy lại `install.sh` rồi `./ns3 build`.

## Hoặc dùng Docker

```bash
docker build -f simulation/Dockerfile -t caar-ns3 .
docker run --rm -v "$PWD:/repo" caar-ns3 python3 scripts/check_ns3.py --ns3 /opt/ns-3-dev --out /tmp/check
docker run --rm -v "$PWD:/repo" -e NS3_DIR=/opt/ns-3-dev caar-ns3 scripts/run_batch.sh s1 s2a s2b
```

## Chạy một kịch bản

```bash
cd ~/ns-3-dev
./ns3 run "caar --config=cloud_assisted --scenario=outage --seed=1 --nodes=10 \
  --waypoints=$REPO/contracts/waypoints/10_1.csv --channel=$REPO/contracts/channel.json \
  --ttl=60 --dmax=20 --outage-start=300 --outage-end=600 \
  --out=$REPO/results/raw/cloud_assisted_outage_1.csv"
./ns3 run "caar --help"     # mọi tham số
```

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--config` | `no_cloud` | `no_cloud` \| `local_optimized` \| `gateway_heuristic` \| `cloud_assisted` |
| `--scenario` | `baseline` | Ghi vào cột `scenario` |
| `--seed` | 1 | `RngRun`; cùng seed cho cùng kết quả |
| `--nodes` | 10 | Số robot, phải khớp file waypoints |
| `--dmax`, `--jitter` | 20, 2 ms | D_i = D_max · c_i + U(0, J) |
| `--ttl`, `--period`, `--cloud-timeout` | 60, 5, 2 s | Gateway (mục 7.3) |
| `--outage-start`, `--outage-end` | −1 (không mất) | Mất WAN trong khoảng này |
| `--wan-trace` | trống | `contracts/wan_trace.csv`; trống thì RTT hằng số `--wan-rtt-ms` (40 ms) |
| `--fixed-weights` | trống | Ghi đè trọng số `local_optimized`, ví dụ `1,0,0` (kiểm tra w_h = 1) |
| `--window-start`, `--window-end` | 300, 600 s | Cửa sổ tính `params.pdr_window` (dùng cho Q3) |
| `--speed` | 0,2 | Ghi vào cột `mobility_speed` |
| `--netanim`, `--netanim-start`, `--netanim-stop` | tắt, 0, cuối | File XML NetAnim và cửa sổ ghi gói tin |
| `--drain-move`, `--drain-tx` | 0,02 %/s, 0,001 %/gói | Hao pin (mục 6.3) |

## Mô hình trong `caar.cc`

- Node 0 là Gateway (vị trí trong `contracts/waypoints/layout.json`), robot là node 1..N theo file waypoints.
- WiFi 802.11b ad hoc 1 Mbps; công suất phát và ngưỡng thu lấy từ `channel.json` (20 dBm / −88 dBm);
  ngưỡng phát hiện preamble đặt bằng ngưỡng thu, độ nhạy dưới −90 dBm bị từ chối;
  kênh `LogDistancePropagationLossModel` + `RandomPropagationLossModel` (chuẩn, σ).
- Mỗi robot gửi UDP 128 B/s tới Gateway (cổng 9). Gói mang pin và RSSI trung bình của
  robot, nên Gateway dựng `NetworkSnapshot` từ chính gói nhận được.
- RSSI theo hàng xóm: EWMA (α = 0,1) trên trace `MonitorSnifferRx`.
- `no_cloud` không gắn hook nên AODV chạy đúng như bản gốc (jitter U(0, 10) ms).
- `cloud_assisted`: mỗi T giây Gateway lấy ngẫu nhiên một dòng trace WAN; timeout, lỗi HTTP
  hoặc đang mất cloud thì báo lỗi sau 2 s, ngược lại trả trọng số sau RTT.
- Trọng số Gateway nhận được áp dụng ngay cho mọi robot (không mô phỏng gói phát trọng số).
- `cloud_bandwidth_bytes`: tổng byte JSON request + response, không tính header HTTP/TLS.

## Xem mô phỏng bằng NetAnim

`caar` ghi trace NetAnim khi có `--netanim=<file.xml>`. Robot đổi màu theo pin (xanh lá → đỏ,
nhãn `r3 57%`), Gateway đổi màu theo mức hạ cấp (xanh dương L1 → cam L2 → đỏ L3).

```bash
./ns3 run "caar --config=cloud_assisted --scenario=outage --seed=1 --nodes=10   --waypoints=$REPO/contracts/waypoints/10_1.csv --channel=$REPO/contracts/channel.json   --ttl=60 --outage-start=300 --outage-end=600   --netanim=$REPO/results/anim/outage_1.xml --netanim-start=290 --netanim-stop=320"
```

Vị trí robot được ghi cả 900 s; gói tin chỉ ghi trong `--netanim-start`..`--netanim-stop`
để file không quá lớn (cửa sổ 30 s ≈ 1 MB). `results/anim/*.xml` không được commit (`.gitignore`).

Trình xem NetAnim 3.109 (khớp `ver="netanim-3.109"` trong file) build được trên Ubuntu 20.04
(đã thử: g++ 9.4, Qt 5.12.8), không cần ns-3:

```bash
sudo apt install qtbase5-dev qt5-qmake g++ make git
git clone --depth 1 --branch netanim-3.109 https://gitlab.com/nsnam/netanim.git ~/netanim
cd ~/netanim && qmake NetAnim.pro && make -j4
./NetAnim      # File > Open > chọn file .xml, rồi bấm Play
```

## Kiểm tra (mục 14.3)

```bash
python3 scripts/check_ns3.py --ns3 ~/ns-3-dev --out /tmp/caar-check --seeds 5
```

Chạy cả trên CI (job `ns3`).
