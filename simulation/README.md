# simulation/ — NS-3 (ns-3.48)

| Thư mục / file | Nội dung |
|---|---|
| `aodv-patch/caar-delayed-rreq.patch` | Patch `src/aodv`: hook thời gian chờ rebroadcast RREQ + trace `RouteDiscovery` |
| `scratch/caar.cc` | Kịch bản 4 cấu hình (mục 10.1), đọc `contracts/`, ghi CSV kết quả, trace NetAnim và cảnh 3D NetSimulyzer |
| `caar-logic/caar_logic.h` | Heuristic, chi phí c_i, máy trạng thái Gateway (C++ thuần, có parity test) |
| `install.sh` | Áp patch (bỏ qua nếu đã áp) và chép `caar.cc` + `caar_logic.h` vào `scratch/caar/` |
| `vm/setup-ubuntu.sh`, `vm/demo.sh` | Cài và chạy trên Ubuntu 24.04, xem bằng NetAnim (2D) và NetSimulyzer (3D) |
| `vm/netanim-wpr.patch` | Cho NetAnim 3.109 vẽ được gói wifi của ns-3 |
| `netsimulyzer/models/caar/` | Mô hình 3D khung thép, kính, hàng cà chua cho trình xem NetSimulyzer (`scripts/gen_greenhouse_models.py`) |
| `Dockerfile` | Ubuntu 24.04 + ns-3.48 đã cài CAAR |

## Cài trên Ubuntu 24.04 (máy ảo hoặc máy thật)

```bash
git clone -b cloud/network-snapshot https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131
bash simulation/vm/setup-ubuntu.sh     # gói hệ thống, ns-3.48 + CAAR + NetSimulyzer vào ~/ns-3-dev, NetAnim vào ~/netanim
bash simulation/vm/demo.sh             # chạy 1 kịch bản, ghi trace + cảnh 3D vào results/demo/, mở NetAnim
```

`setup-ubuntu.sh` in từng bước và chạy lại an toàn (bước đã xong thì bỏ qua). Build ns-3 dùng số
luồng theo RAM (~1,5 GB/luồng); máy cần ít nhất 4 GB RAM và 15 GB ổ trống.
`demo.sh [config] [scenario] [seed] [số robot]`, ví dụ `bash simulation/vm/demo.sh no_cloud baseline`.

Các lệnh tương đương nếu cài tay:

```bash
sudo apt install g++ cmake ninja-build python3 git patch ccache
git clone --depth 1 --branch ns-3.48 https://gitlab.com/nsnam/ns-3-dev.git ~/ns-3-dev
simulation/install.sh ~/ns-3-dev
git clone --depth 1 --branch v1.0.17 https://github.com/usnistgov/NetSimulyzer-ns3-module.git \
  ~/ns-3-dev/contrib/netsimulyzer          # tùy chọn: cảnh 3D (--netsimulyzer)
cd ~/ns-3-dev
./ns3 configure --build-profile=release --disable-examples --disable-tests \
  --enable-modules="aodv;wifi;mobility;internet;applications;flow-monitor;propagation;netanim;netsimulyzer"
./ns3 build
```

Không cần 3D thì bỏ bước clone và bỏ `;netsimulyzer` khỏi `--enable-modules`; `caar.cc` vẫn build
được (CI và Docker build theo cách này), chỉ có `--netsimulyzer` báo lỗi.

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
| `--netsimulyzer` | tắt | File JSON cảnh 3D cho NetSimulyzer (cần module `contrib/netsimulyzer`) |
| `--netsimulyzer-env` | bật | Cảnh 3D có khung thép, kính, hàng cà chua (cần chép `models/caar` vào trình xem) |
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
`r3 57%`), Gateway đổi màu theo mức hạ cấp (xanh dương L1 → cam L2 → đỏ L3). Gói tin chỉ ghi
trong `--netanim-start`..`--netanim-stop` để file không quá lớn (30 s ≈ 1 MB). Vị trí robot do
`caar` tự ghi mỗi giây trong cả lượt chạy: AnimationInterface của ns-3.48 chỉ ghi vị trí trong cửa
sổ ghi gói, và cả trong đó cũng bỏ sót vì mỗi lần node gửi gói nó cập nhật vị trí đã lưu mà không
ghi ra file. File XML không được commit.

Trình xem NetAnim 3.109 khớp phiên bản trace (`ver="netanim-3.109"`), không cần ns-3.
NetAnim 3.109 đọc bản ghi gói wifi `<pr>` + `<wpr>` của ns-3 nhưng không vẽ;
`vm/netanim-wpr.patch` sửa phần đọc file để vẽ được. `setup-ubuntu.sh` đã áp patch và build sẵn;
build tay:

```bash
sudo apt install qtbase5-dev qt5-qmake libqt5svg5 g++ make git patch
git clone --depth 1 --branch netanim-3.109 https://gitlab.com/nsnam/netanim.git ~/netanim
patch -d ~/netanim -p1 < simulation/vm/netanim-wpr.patch
cd ~/netanim && qmake NetAnim.pro && make -j4
```

Xem gói tin: mở file bằng biểu tượng thư mục; gõ thời điểm bắt đầu cửa sổ (ví dụ 290) vào
Pause At, kéo thanh fast–slow về fast và bấm Play để chạy nhanh tới đó; rồi kéo thanh về giữa và bấm
Play. Mỗi gói hiện trong một bước phát. Kéo thanh Sim time là tua nhanh, NetAnim không vẽ gói trong
đoạn tua.

## Xem 3D bằng NetSimulyzer

`caar --netsimulyzer=<file.json>` ghi cảnh 3D cho [NetSimulyzer](https://github.com/usnistgov/NetSimulyzer)
(NIST) 1.0.17, cả 900 s (≈ 3 MB với 10 robot):

| Trong cảnh | Lấy từ |
|---|---|
| Nền nhà kính 100 × 100 m, lối đi giữa, 112 ray | `contracts/waypoints/layout.json` |
| Khung thép kiểu Venlo (11 nhịp ~9 m, máng xối 4,5 m, đỉnh mái 5,6 m, cột mỗi 5 m, kèo, giằng), kính mái và vách, cửa hai đầu lối đi | `netsimulyzer/models/caar/frame.obj`, `glass.obj` |
| 110 hàng cà chua (máng giá thể, thân, lá, quả chín và xanh), mỗi hàng giữa hai ray | `netsimulyzer/models/caar/plant_row.obj` |
| Gateway (cột anten), tên `Gateway L1/L2/L3`, màu xanh dương / cam / đỏ theo mức hạ cấp | máy trạng thái Gateway |
| Robot (xe), vệt di chuyển, màu và nhãn theo pin (`r3 57%`) | quỹ đạo waypoints, pin mỗi 5 s |
| Vòng phát mỗi lần robot gửi gói telemetry | `SendTelemetry` |
| Đường robot → hop kế tiếp về Gateway: xanh dương = thẳng tới Gateway, cam = qua robot khác | bảng AODV của robot (route `UP`), đọc mỗi giây |
| Biểu đồ: PDR theo khung 10 s, số robot có đường về Gateway, pin thấp nhất, mức Gateway | bộ đếm gói, bảng AODV, pin, Gateway |
| Log `Gateway` (param_update + luật, outage_start, stale_detected, outage_end) và `Định tuyến AODV` | như `_events.csv`; đổi hop kế tiếp |
| Chỉ `cloud_assisted`: máy chủ Cloud (mô hình `server`) phía bắc nhà kính, đường Gateway–Cloud xanh lá / cam / đỏ theo L1/L2/L3, vòng sáng ở Gateway mỗi lần gọi `/optimize` và ở Cloud khi trả lời | kênh Cloud mô phỏng trong `GatewayTick` (RTT 40 ms, timeout 2 s) |
| Chỉ `cloud_assisted`: log `Cloud` (mỗi lần gọi: byte gửi, byte nhận, RTT, luật; hoặc timeout) và biểu đồ byte trao đổi với Cloud cộng dồn | `SnapshotBytes`, `kResponseBytes`, `g_cloudBytes` |

Cloud trong mô phỏng không phải node mạng: `GatewayTick` chạy cùng heuristic với dịch vụ FastAPI
(`caar::ChooseWeights`, khớp bản Python qua `contracts/parity_cases.json`) và trả kết quả sau RTT hằng
số; node "Cloud" trong cảnh 3D không có card mạng hay IP, chỉ để vẽ máy chủ và đường nối.

Cảnh chỉ đọc trạng thái mô phỏng (không thêm biến ngẫu nhiên, gói tin hay thay đổi định tuyến; in
bảng AODV làm trên bản sao), nên CSV và `_events.csv` giống hệt lượt chạy không bật 3D; `check_ns3.py`
nhóm 8 kiểm tra điều này. File JSON không được commit.

Trình xem là ứng dụng riêng, không cần ns-3:

- Windows: tải `NetSimulyzer-v1.0.17-windows.zip` ở
  [trang release](https://github.com/usnistgov/NetSimulyzer/releases/tag/v1.0.17), giải nén, chạy
  `netsimulyzer.exe`. Chép file `.json` từ máy ảo ra (ví dụ `scp -P 2222 user@127.0.0.1:...`).
- Ubuntu 24.04: cần Qt 6.4 và OpenGL 3.3 (máy ảo VirtualBox dùng OpenGL phần mềm nên chậm):
  ```bash
  sudo apt install build-essential cmake pkg-config qt6-base-dev qt6-base-private-dev \
    qt6-wayland-dev qt6-wayland-private-dev libassimp-dev zlib1g-dev
  git clone --recursive --branch v1.0.17 https://github.com/usnistgov/NetSimulyzer.git ~/netsimulyzer-app
  cd ~/netsimulyzer-app && mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release .. && make -j2
  ```

Chép mô hình nhà kính vào trình xem (một lần), nếu không cảnh chỉ có nền và ray:

```bash
# Windows (PowerShell), từ thư mục repo:
Copy-Item -Recurse simulation\netsimulyzer\models\caar <thư mục trình xem>\resources\models\
# Ubuntu, trình xem build ở ~/netsimulyzer-app:
cp -r simulation/netsimulyzer/models/caar ~/netsimulyzer-app/resources/models/
```

Mô hình sinh từ `layout.json` bằng `python scripts/gen_greenhouse_models.py` (đổi layout thì chạy
lại; test `test_greenhouse_models_match_generator` báo khi file đã commit lệch với script). Cột thép
đặt giữa ray và hàng cây nên không chắn đường robot. Không cần môi trường thì chạy với
`--netsimulyzer-env=0`.

Trong trình xem: **File > Load** chọn file `.json` (truyền đường dẫn trên dòng lệnh không mở được file).
**Camera > Arc Ball** rồi cuộn chuột để nhìn bao quát; **Jump** nhập `05:00.000000000` để tới lúc mất
cloud; ▶ để chạy. Log ở khung **Log** (danh sách thả xuống chọn `Gateway`, `Định tuyến AODV` hoặc
`Unified Log`); biểu đồ ở khung **Chart Widget** (mở từ menu **Window**), chọn series ở
**Select Series**.

## Kiểm tra (mục 14.3)

```bash
python3 scripts/check_ns3.py --ns3 ~/ns-3-dev --out /tmp/caar-check --seeds 5
```

CI chạy kiểm tra này ở job `ns3` mỗi lần push. CI không cài NetSimulyzer nên bỏ qua nhóm 8; chạy
trên máy ảo đã cài module thì có nhóm 8.
