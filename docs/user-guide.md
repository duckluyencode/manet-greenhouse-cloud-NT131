# Hướng dẫn sử dụng

## 1. Chạy mô phỏng trên Ubuntu 24.04

Máy ảo hoặc máy thật, cần ít nhất 4 GB RAM và 15 GB ổ trống.

```bash
git clone -b cloud/network-snapshot https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131
bash simulation/vm/setup-ubuntu.sh
bash simulation/vm/demo.sh
```

`setup-ubuntu.sh` cài gói hệ thống, ns-3.48 kèm CAAR vào `~/ns-3-dev` và NetAnim 3.109 vào
`~/netanim`; chạy lại thì bỏ qua bước đã xong.

`demo.sh [config] [scenario] [seed] [số robot]` (mặc định `cloud_assisted outage 1 10`) chạy một
kịch bản 900 s, ghi `results/demo/<tên>.csv` và trace `results/demo/<tên>.xml`, rồi mở NetAnim.

Trong NetAnim: File > Open, chọn file `.xml`, bấm Play.

| Màu | Ý nghĩa |
|---|---|
| Robot xanh lá → đỏ | Pin còn nhiều → ít (nhãn `r3 57%`) |
| Gateway xanh dương | Mức 1: trọng số từ Cloud |
| Gateway cam | Mức 2: mất Cloud, dùng trọng số cache |
| Gateway đỏ | Mức 3: cache quá TTL, dùng bộ cân bằng |

Gói tin chỉ được vẽ trong khoảng 290–320 s (quanh lúc mất Cloud ở giây 300); kéo thanh thời
gian tới đó. Tham số của `caar`: [`simulation/README.md`](../simulation/README.md).

## 2. Chạy toàn bộ thí nghiệm

```bash
NS3_DIR=~/ns-3-dev scripts/run_batch.sh s1 s2a s2b s3 sens diag
python scripts/import_ns3_results.py --db results/results.db
python scripts/plot_results.py --db results/results.db --out results/figures
```

| Kịch bản | Nội dung | Câu hỏi |
|---|---|---|
| `s1` | baseline, 4 cấu hình, 10 robot | Q1, Q2a, Q2b |
| `s2a` | `cloud_assisted`, mất Cloud 300–600 s, TTL 60 s | Q3 |
| `s2b` | như `s2a` với TTL 15, 60, 300 s | Q3 |
| `s3` | 4 cấu hình, 6, 10, 16, 20 robot | Q1 theo mật độ |
| `sens` | D_max 5, 10, 20 ms; tốc độ 1 m/s | độ nhạy |
| `diag` | chỉ Gateway trả lời RREQ, 10 và 20 robot; thêm D_max 500 ms với 10 robot (`hook`) | chẩn đoán Q1 |

Mỗi kịch bản chạy 10 seed (`SEEDS="1 2 3"` để chạy ít hơn). Run đã có file kết quả thì bỏ qua,
nên chạy lại sau khi bị ngắt sẽ tiếp tục. `scripts/run_batch.sh --dry-run all` chỉ in lệnh.

`results/figures/hypotheses.md` ghi kết luận Q1–Q3 theo tiêu chí mục 10.5.
Truy vấn SQL mẫu ở mục 13.6 của tài liệu đồ án.

## 3. Chạy Cloud Service

Local:

```bash
cd cloud-service
pip install -r requirements.txt
export CAAR_API_KEY=dev-key        # Windows: set CAAR_API_KEY=dev-key
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health  # {"status":"ok"}
```

Trên EC2 (mục 13.3): Ubuntu 24.04 ở ap-southeast-1, có Elastic IP; security group mở cổng 22
(chỉ IP quản trị), 80 và 443. Tên miền có thể dùng `<IP, dấu chấm thay bằng gạch>.sslip.io`,
ví dụ `52-221-14-120.sslip.io`, để Caddy xin chứng chỉ Let's Encrypt.

```bash
sudo apt install -y docker.io docker-compose-v2 git
git clone -b cloud/network-snapshot https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131
cp deploy/.env.example deploy/.env      # điền CAAR_API_KEY, CAAR_DOMAIN; chmod 600 deploy/.env
sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
curl https://<tên-miền>/health
```

Dừng instance khi không demo.

## 4. Gọi /optimize

```bash
curl -X POST https://<tên-miền>/optimize \
  -H "Content-Type: application/json" -H "X-API-Key: $CAAR_API_KEY" \
  -d "{\"run_id\": 1, \"timestamp\": $(date +%s), \"nodes\": [
        {\"node_id\": \"r1\", \"rssi_avg\": -72, \"energy_remaining_pct\": 45, \"hop_count\": 2},
        {\"node_id\": \"r2\", \"rssi_avg\": -85, \"energy_remaining_pct\": 12, \"hop_count\": 3}]}"
# {"weights":{"hop_weight":0.2,"rssi_weight":0.3,"energy_weight":0.5},"rule":"low_battery"}
```

`timestamp` phải là thời điểm hiện tại; lệch quá 30 s bị từ chối (400).

## 5. Demo bảo mật (mục 8)

| Thử | Lệnh | Kết quả |
|---|---|---|
| Gọi trái phép | bỏ header `X-API-Key` | 401 |
| Replay | gửi lại body có `timestamp` cũ hơn 30 s | 400 |
| Replay cùng nonce | gửi cùng body có `"nonce": "abc"` hai lần | lần 2: 400 |
| Dữ liệu rác | `"energy_remaining_pct": 150` | 422 |
| Nghe lén | `curl http://<tên-miền>/health` | Caddy chuyển sang HTTPS |

## 6. Sự kiện trong cloud_events

| `event_type` | Ý nghĩa |
|---|---|
| `param_update` | Trọng số mới (Cloud ghi mỗi lần trả lời; Gateway ghi khi áp dụng) |
| `outage_start` | Gateway gọi Cloud lỗi lần đầu, chuyển mức 2 (dùng cache) |
| `stale_detected` | Tuổi cache ≥ TTL, chuyển mức 3 (bộ cân bằng) |
| `outage_end` | Cloud trả lời lại, quay về mức 1 |
