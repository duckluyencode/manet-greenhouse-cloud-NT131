# Khảo sát quy mô nhà kính và robot — cơ sở chọn môi trường mô phỏng

Cập nhật 26/10/2026. Mục đích: chọn diện tích, bố trí, số robot và tốc độ robot sát
thực tế. Khi các nguồn khác nhau, **ưu tiên môi trường gần với số liệu đồ án đang dùng**,
tức nhà kính cà chua nơi Cama-Pinto et al. (2019) đo kênh truyền (mục 5) và các robot
pipe-rail đã có số liệu vận hành (mục 6.1).

## 1. Quy mô nhà kính theo vùng

| Vùng | Số liệu | Nguồn |
|---|---|---|
| Almería, Tây Ban Nha (nơi đo kênh) | 4 nhà kính cà chua, **mỗi nhà 10.000 m²**, hành lang chính 100 m, lối đi 1,2 m, cây cách 50 cm, hàng đôi cách 60 cm | [Cama-Pinto et al. 2019, mục 2.10](https://pmc.ncbi.nlm.nih.gov/articles/PMC6572486/) |
| Almería | Quy mô trung bình **~2 ha/công ty** (Delphy, 12/2018) | [HortiDaily](https://hortidaily.com/article/9051879/almeria-a-formidable-competitor-in-fruit-vegetable-cultivation) |
| Almería | 32.827 ha nhà kính, cà chua 8.187 ha (vụ 2020/21) | [FreshPlaza](https://www.freshplaza.com/europe/article/9485101/almeria-increased-its-32-827-hectares-of-greenhouses-to-almost-48-000-hectares-by-having-two-cultivation-cycles/) |
| Hà Lan | Cà chua kính ~1.700 ha; 10 trang trại lớn nhất giữ ~850 ha, ~200 trang trại còn lại chia ~850 ha (trung bình tự tính ~8 ha/trang trại) | [HortiDaily](https://hortidaily.com/article/9702261/scale-up-in-greenhouse-tomatoes-in-the-netherlands-continues) |
| Canada (Essex, Ontario) | 135 doanh nghiệp trên 1.300 ha (trung bình tự tính ~9,6 ha), 08/2023 | [The Globe and Mail](https://www.theglobeandmail.com/business/article-windsor-greenhouse-growers-infrastructure) |
| Việt Nam (Lâm Đồng) | Tiêu chí sản xuất rau công nghệ cao: tối thiểu **3.000 m²/hộ, 9.000 m²/doanh nghiệp, HTX** | [QĐ 1470/QĐ-UBND, 2021](https://caselaw.vn/van-ban-phap-luat/362035-quyet-dinh-so-1470-qd-ubnd-ngay-09-06-2021-ve-quy-dinh-tam-thoi-tieu-chi-san-xuat-nong-nghiep-ung-dung-cong-nghe-cao-tren-dia-ban-tinh-lam-dong) |
| Việt Nam (Đà Lạt) | Khoảng 20 % nhà kính được đầu tư bài bản, nhiều nơi vẫn thu hoạch thủ công | [SGGP](https://www.sggp.org.vn/rau-nha-kinh-co-an-toan-post533872.html) |

Trang trại châu Âu và Bắc Mỹ lớn (vài ha tới hàng chục ha) nhưng chia thành nhiều khoang
(compartment); một khoang 1 ha với một Gateway là đơn vị hợp lý cho mạng MANET.

## 2. Bố trí bên trong

| Thông số | Số liệu | Nguồn |
|---|---|---|
| Bước hàng | Lối đi 1,2 m + hàng đôi 0,6 m = 1,8 m; điểm đo cách nhau ~1,8 m | Cama-Pinto 2019, mục 2.10, Bảng 2 |
| Hành lang chính | 100 m (nhà 1 ha) | Cama-Pinto 2019, mục 2.10 |
| Hành lang trung tâm | Ví dụ khu nhà kính 13 ha có hành lang trung tâm 9 m, ray ống sưởi | [HortiDaily (VB Group)](https://hortidaily.com/article/6003001/vb-group-constructing-13-hectare-state-of-the-art-greenhouse-in-russia) |
| Chiều dài hàng | 34 m mỗi hàng (6 hàng/khoang, ĐH Bonn) | [PATHoBot, arXiv 2010.16272](https://arxiv.org/html/2010.16272v2) |
| Ray ống sưởi | Ống sưởi trên nền dùng làm ray cho máy móc | PATHoBot; [HortiDaily (Venlo, Ireland)](https://www.hortidaily.com/article/6030625/irish-tomato-grower-expands-greenhouse-business/) |

## 3. Robot: mật độ và tốc độ

| Loại | Số liệu | Nguồn |
|---|---|---|
| Robot thu hoạch cà chua bi (inaho, thử ở Hà Lan) | **4 robot ~ 1 ha**, 20 kg/giờ | [HortiDaily](https://www.hortidaily.com/article/9778303/harvest-robot-for-snack-tomatoes-commercial-ready/) |
| Robot thu hoạch (Tokuiten, Nhật) | Kế hoạch 6 robot cho nhà kính 1 ha | [HortiDaily](https://www.hortidaily.com/article/9842754/japanese-agri-tech-startup-puts-cherry-tomato-harvesting-robot-into-routine-production-use/) |
| Robot thụ phấn | 3,5 robot/ha (số liệu nhà cung cấp) | [Service Robot Co.](https://servicerobotco.com/case-studies/how-a-tomato-greenhouse-lifted-yield-up-to-20-with-robot-pollination) |
| Robot tỉa lá Kompano (Priva) | ~1 ha/tuần mỗi robot, chạy trên ray, tới 24 giờ/ngày | [Greentech](https://www.greentech.nl/news/robotics-ai/priva-introduced-kompano-the-worlds-first-fully-automated-leaf-cutting-robot-for-tomato-crops) |
| PATHoBot (quét cây) | **~0,2 m/s** khi quét | [arXiv 2010.16272](https://arxiv.org/html/2010.16272v2) |
| Xe ray ống thương mại (Berg Hortimotive) | Tối đa 60–70 m/phút (1,0–1,17 m/s), lái tay | [Benomic](https://www.hortispares.com/machines/benomic/), [BRW150](https://www.hortispares.com/machines/brw-150/) |
| Việt Nam | Robot thu hoạch trong nhà kính mới ở mức nghiên cứu (ĐH Công nghệ, ĐHQGHN), chưa có số liệu triển khai thương mại | [Đại biểu Nhân dân](https://daibieunhandan.vn/giang-vien-dh-cong-nghe-che-tao-thanh-cong-san-pham-robot-thu-hoach-hoa-qua-trong-nha-kinh-10302457.html), [Nông nghiệp & Môi trường](https://nongnghiepmoitruong.vn/nghien-cuu-che-tao-thanh-cong-robot-thu-hai-hoa-qua-d301996.html) |

## 4. Môi trường mô phỏng đã chọn

| Thông số | Giá trị | Lý do |
|---|---|---|
| Diện tích | 100 × 100 m (1 ha) | Bằng nhà kính đo kênh (Cama-Pinto); khớp ngưỡng doanh nghiệp ở Lâm Đồng (≥ 0,9 ha); nhỏ hơn quy mô trang trại châu Âu/Bắc Mỹ nhưng bằng một khoang |
| Lối chính | Ở giữa (y = 47,5–52,5 m), dài 100 m | Hành lang chính 100 m (Cama-Pinto); hành lang trung tâm có ví dụ thực tế |
| Hàng ray | 112 hàng × 47,5 m, hai phía lối chính, bước 1,8 m | Bước hàng của Cama-Pinto; độ dài cùng cỡ PATHoBot (34 m) |
| Gateway | (50; 50), giữa lối chính | Mục 6.2 của tài liệu đồ án |
| Số robot mặc định | 10 | Đội hỗn hợp trên 1 ha: thu hoạch 4–6 + thụ phấn ~3,5 + tỉa lá/quét ~1 |
| Quét số robot (S3) | 6, 10, 16, 20 | 6 ≈ chỉ robot thu hoạch; 16–20 là đội dày |
| Tốc độ trên ray | 0,2 m/s | PATHoBot ~0,2 m/s |
| Tốc độ cho kịch bản độ nhạy | 1 m/s | Xe ray thương mại 1,0–1,17 m/s |
| Radio | WiFi 20 dBm, anten 3 dBi mỗi đầu, ngưỡng thu −82 dBm (ngân sách 108 dB, tầm 29,35 m) | Ngưỡng thu bằng ngưỡng phát hiện preamble của ns-3.48; thấp hơn −82 dBm thì PHY của ns-3.48 có lúc dừng |

Hệ quả đo được (kết nối hình học: robot có đường về Gateway, tầm 29,35 m, 3 seed):

| Robot / 1 ha | 6 | 10 | 16 | 20 |
|---|---|---|---|---|
| Có đường về Gateway | 29 % | 50 % | 84 % | 89 % |

Ở mật độ robot thực tế, mạng bị chia cắt phần lớn thời gian; định tuyến chỉ cải thiện được
phần gói mất khi đường đi còn tồn tại. Kịch bản S3 đo đúng điểm này.

## 5. Điểm chưa khớp hoàn toàn

- Nhà kính Almería thường là nhà plastic không sưởi bằng ống, trong khi robot pipe-rail là
  đặc trưng của nhà kính kính có sưởi (Hà Lan, Anh). Đồ án ghép kênh truyền đo ở Almería với
  kiểu di chuyển pipe-rail; đây là giả định cần nêu khi bảo vệ.
- Chiều rộng lối chính (5 m) không có số đo trong Cama-Pinto; ví dụ thương mại có 9 m.
- Mật độ robot là số liệu nhà cung cấp hoặc kế hoạch, chưa có thống kê độc lập; Việt Nam
  chưa có số liệu triển khai.
