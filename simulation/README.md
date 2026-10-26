# simulation/ — NS-3 (ns-3.48)

| Thư mục / file | Nội dung |
|---|---|
| `aodv-patch/caar-delayed-rreq.patch` | Patch `src/aodv`: hook thời gian chờ rebroadcast RREQ + trace `RouteDiscovery` |
| `scratch/caar.cc` | Kịch bản 4 cấu hình (mục 10.1), đọc `contracts/`, ghi CSV kết quả và trace NetAnim |
| `caar-logic/caar_logic.h` | Heuristic, chi phí c_i, máy trạng thái Gateway (C++ thuần, có parity test) |
| `install.sh` | Áp patch (bỏ qua nếu đã áp) và chép `caar.cc` + `caar_logic.h` vào `scratch/caar/` |
| `vm/setup-ubuntu.sh`, `vm/demo.sh` | Cài và chạy trên Ubuntu 24.04, xem bằng NetAnim |
| `Dockerfile` | Ubuntu 24.04 + ns-3.48 đã cài CAAR |

## Cài trên Ubuntu 24.04 (máy ảo hoặc máy thật)

```bash
git clone -b cloud/network-snapshot https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131
bash simulation/vm/setup-ubuntu.sh     # gói hệ thống, ns-3.48 + CAAR vào ~/ns-3-dev, NetAnim vào ~/netanim
bash simulation/vm/demo.sh             # chạy 1 kịch bản, ghi trace vào results/demo/, mở NetAnim
```

`setup-ubuntu.sh` in từng bước và chạy lại an toàn (bước đã xong thì bỏ qua). Build ns-3 dùng số
luồng theo RAM (~1,5 GB/luồng); máy cần ít nhất 4 GB RAM và 15 GB ổ trống.
`demo.sh [config] [scenario] [seed] [số robot]`, ví dụ `bash simulation/vm/demo.sh no_cloud baseline`.

Các lệnh tương đương nếu cài tay:

```bash
sudo apt install g++ cmake ninja-build python3 git patch ccache
git clone --depth 1 --branch ns-3.48 https://gitlab.com/nsnam/ns-3-dev.git ~/ns-3-dev
simulation/install.sh ~/ns-3-dev
cd ~/ns-3-dev
./ns3 configure --build-profile=release --disable-examples --disable-tests \
  --enable-modules="aodv;wifi;mobility;internet;applications;flow-monitor;propagation;netanim"
./ns3 build
```

Sửa `caar.cc` hoặc `caar_logic.h` trong repo thì chạy lại `install.sh` rồi `./ns3 build`.
Profile `release` giữ `-O3` như `optimized` nhưng không có `-march=native`, nên file chạy dùng
được trên mọi CPU x86-64 và cùng seed cho cùng kết quả trên mọi máy.

## Dùng Docker

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
| `--wan-rtt-ms` | 40 ms | RTT Gateway–Cloud (`contracts/README.md`) |
| `--outage-start`, `--outage-end` | −1 (không mất) | Mất cloud trong khoảng này |
| `--fixed-weights` | trống | Ghi đè trọng số `local_optimized`, ví dụ `1,0,0` (kiểm tra w_h = 1) |
| `--destination-only` | tắt | Chỉ Gateway trả lời RREQ (AODV `DestinationOnly`); dùng cho kịch bản `diag` |
| `--window-start`, `--window-end` | 300, 600 s | Cửa sổ tính `params.pdr_window` (Q3) |
| `--speed` | 0,2 | Ghi vào cột `mobility_speed` |
| `--netanim`, `--netanim-start`, `--netanim-stop` | tắt, 0, cuối | File XML NetAnim và cửa sổ ghi gói tin |
| `--drain-move`, `--drain-tx` | 0,02 %/s, 0,001 %/gói | Hao pin (mục 6.3) |

## Mô hình trong `caar.cc`

- Node 0 là Gateway (vị trí trong `contracts/waypoints/layout.json`), robot là node 1..N theo file waypoints.
- WiFi 802.11b ad hoc 1 Mbps; công suất phát, độ lợi anten và ngưỡng thu lấy từ `channel.json`
  (20 dBm, 3 dBi, 3 dBi, −82 dBm); ngưỡng phát hiện preamble bằng ngưỡng thu; ngưỡng dưới −82 dBm
  bị từ chối vì PHY của ns-3.48 có lúc dừng với "Invalid WifiPhy state RX".
- Kênh `LogDistancePropagationLossModel` + `RandomPropagationLossModel` (phân phối chuẩn, σ).
- Mỗi robot gửi UDP 128 B/s tới Gateway (cổng 9). Gói mang pin và RSSI trung bình của robot, nên
  Gateway dựng `NetworkSnapshot` từ chính gói nhận được.
- RSSI theo hàng xóm: EWMA (α = 0,1) trên trace `MonitorSnifferRx`.
- `no_cloud` không gắn hook nên AODV chạy đúng như bản gốc (jitter U(0, 10) ms).
- `cloud_assisted`: mỗi T giây Gateway gọi Cloud; trọng số về sau RTT, đang mất cloud thì báo lỗi
  sau timeout 2 s và Gateway hạ cấp.
- Trọng số Gateway nhận được áp dụng ngay cho mọi robot (không mô phỏng gói phát trọng số).
- `cloud_bandwidth_bytes`: tổng byte JSON request + response, không tính header HTTP/TLS.

## Xem mô phỏng bằng NetAnim

`caar --netanim=<file.xml>` ghi trace NetAnim. Robot đổi màu theo pin (xanh lá → đỏ, nhãn
`r3 57%`), Gateway đổi màu theo mức hạ cấp (xanh dương L1 → cam L2 → đỏ L3). Vị trí robot được ghi
cả 900 s; gói tin chỉ ghi trong `--netanim-start`..`--netanim-stop` để file không quá lớn
(30 s ≈ 1 MB). File XML không được commit.

Trình xem NetAnim 3.109 khớp phiên bản trace (`ver="netanim-3.109"`), không cần ns-3; mở bằng
File > Open, rồi bấm Play. `setup-ubuntu.sh` đã build sẵn; build tay:

```bash
sudo apt install qtbase5-dev qt5-qmake g++ make git
git clone --depth 1 --branch netanim-3.109 https://gitlab.com/nsnam/netanim.git ~/netanim
cd ~/netanim && qmake NetAnim.pro && make -j4
```

## Kiểm tra (mục 14.3)

```bash
python3 scripts/check_ns3.py --ns3 ~/ns-3-dev --out /tmp/caar-check --seeds 5
```

CI chạy kiểm tra này ở job `ns3` mỗi lần push.
