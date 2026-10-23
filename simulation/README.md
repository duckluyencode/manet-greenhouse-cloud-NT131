# simulation/ — NS-3 module (Owner: A)

Môi trường tạo repo này **không có mạng** nên không tự tải/cài NS-3 giúp bạn được.
Cần cài trên máy của bạn theo các bước dưới đây.

## Cài đặt NS-3 (chạy trên máy bạn)

```bash
# 1. Clone NS-3 và chuyển sang tag cố định ns-3.48 (không dùng nhánh dev)
git clone https://gitlab.com/nsnam/ns-3-dev.git ns-3-dev
cd ns-3-dev
git checkout ns-3.48
git describe --tags   # phải hiện đúng "ns-3.48"

# 2. Cấu hình + build (lần đầu khá lâu, 20-40 phút tùy máy)
./ns3 configure --build-profile=optimized --enable-examples
./ns3 build -j4

# 3. Kiểm tra AODV mẫu chạy được
./ns3 run aodv-example
# Kỳ vọng: gói đầu chậm (vài trăm ms đến vài giây), các gói sau nhanh dần (~7-8 ms)
```

> Phiên bản NS-3 phải khớp với tag `ns-3.48` để máy các thành viên và Docker
> build ra kết quả giống nhau. Dockerfile trong thư mục này đã được ghim cùng tag.

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