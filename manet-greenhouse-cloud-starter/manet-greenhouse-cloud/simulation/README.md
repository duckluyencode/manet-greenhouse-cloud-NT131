# simulation/ — NS-3 module (Owner: A)

Môi trường tạo repo này **không có mạng** nên không tự tải/cài NS-3 giúp bạn được.
Cần cài trên máy của bạn theo các bước dưới đây.

## Cài đặt NS-3 (chạy trên máy bạn)

```bash
# 1. Clone NS-3 (bản ổn định, ví dụ ns-3.42 — kiểm tra bản mới nhất trên trang chủ NS-3)
git clone https://gitlab.com/nsnam/ns-3-dev.git ns-3-dev
cd ns-3-dev

# 2. Cấu hình + build (lần đầu khá lâu, 10-30 phút tùy máy)
./ns3 configure --enable-tests --enable-examples
./ns3 build

# 3. Kiểm tra AODV mẫu có sẵn chạy được không
./ns3 run "aodv --help"
```

> Khuyến nghị: đóng gói bước trên vào 1 Dockerfile chung cho cả nhóm (Master Plan
> Risk R1) để tránh lệch phiên bản giữa 2 máy — đây là task Day 5 trong Daily Plan.

## Cấu trúc dự kiến trong thư mục này

```
simulation/
├── model/     # mobility model nhà kính (row-constrained), channel/attenuation model
├── helper/    # helper class dựng scenario (3 cấu hình: no_cloud/local_optimized/cloud_assisted)
└── test/      # NS-3 test suite (Owner A, Week 3, DoD-Test)
```

## Việc cần làm (đối chiếu Master Plan — Section 5)

| Ngày | Việc | Ghi chú |
|---|---|---|
| Day 15-16 | Mobility model row-constrained | Không dùng Random Waypoint mặc định — xem lý do ở `bao-ve-thu-qa-workflow-topology.md` Phần B |
| Day 17 | Channel/attenuation model | Suy hao khung kim loại + tán lá; tham số hóa theo giai đoạn sinh trưởng để phục vụ Scenario S8 (Dual-Horizon) sau này |
| Day 18 | Tích hợp AODV baseline (có sẵn trong NS-3) + unit test | DoD-Dev + DoD-Test |
| Day 22 | Local-Optimized AODV variant | Sửa metric: RSSI + hop-count + năng lượng còn lại |
| Day 23 | Cloud-Assisted variant — wiring bridge tới `cloud-service/` | Đọc/ghi tham số qua file hoặc socket cục bộ, có timeout → graceful degradation khi Cloud không phản hồi |
