# Thay đổi so với thiết kế Bài tập 1

Mỗi thay đổi ghi ba dòng: **Thay đổi gì · Vì sao · Ảnh hưởng tới thành phần nào.**
Phần lớn thay đổi xuất phát từ việc **đo bộ dữ liệu thật** (không có kênh bán, phương thức thanh toán, giá vốn, trạng
thái đơn) — BT1 viết trước khi có số đo này.

### TD-01 · `dim_channel` chỉ có 1 kênh
- **Thay đổi:** BT1 thiết kế 5 kênh (Website, App, POS, Shopee, TikTok Shop); kho hiện có duy nhất `POS — Cửa hàng`.
- **Vì sao:** `orders_2024_2026.csv` không có cột kênh; mọi đơn gắn một trong 24 mã cửa hàng `MMxxx`. Tự gán kênh là bịa dữ liệu.
- **Ảnh hưởng:** FR-05, FR-08, Màn hình 3 (có ghi chú giải thích trên giao diện). Bảng và khoá vẫn giữ để khi có nguồn đa kênh chỉ cần thêm dòng.

### TD-02 · `dim_payment` suy ra từ ghi chú đơn
- **Thay đổi:** BT1: COD / Chuyển khoản / Thẻ / Ví MoMo → hiện thực: `TRA_GOP` (ghi chú “Trả góp 0%”) và `TRA_THANG` (còn lại).
- **Vì sao:** Nguồn không có cột phương thức thanh toán; ghi chú “Trả góp 0%” là tín hiệu duy nhất đo được (16,6% đơn).
- **Ảnh hưởng:** FR-09, Màn hình 3, hàm `rules.phan_loai_thanh_toan`, test `test_cong_thuc_chi_so_dong_hang`.

### TD-03 · Giá vốn (`unit_cost`) là ƯỚC TÍNH theo tỷ lệ nhóm sản phẩm
- **Thay đổi:** `unit_cost = gia_niem_yet × ty_le_gia_von` lấy từ `data/reference/ty_le_gia_von.csv` (0,55–0,85 theo nhóm).
- **Vì sao:** `products.csv` chỉ có giá niêm yết, không có giá vốn hay “bình quân gia quyền” như BT1 mô tả.
- **Ảnh hưởng:** FR-10, US6, thẻ KPI “Lợi nhuận gộp (ước tính)”; tỷ lệ là giả định, sửa tệp tham chiếu rồi chạy lại pipeline để cập nhật.

### TD-04 · Hoàn trả = 0 trong công thức doanh thu thuần
- **Thay đổi:** Doanh thu thuần = SL × giá niêm yết − giảm giá − hoàn trả, với hoàn trả = 0; giảm giá = SL × (giá niêm yết − đơn giá bán).
- **Vì sao:** Bộ dữ liệu không có giao dịch trả hàng. Giảm giá đo được vì `don_gia` có lúc bằng 90–95% giá niêm yết.
- **Ảnh hưởng:** `rules.tinh_chi_so_dong_hang`, cột `discount_amount`, `net_revenue`.

### TD-05 · `fact_order_history` (lịch sử trạng thái đơn) chưa hiện thực
- **Thay đổi:** Thay bằng `etl_run_log` append-only (mỗi lần chạy ghi đúng một dòng, không UPDATE).
- **Vì sao:** Đơn hàng trong nguồn không có trạng thái hay mốc chuyển trạng thái — không có gì để ghi lịch sử.
- **Ảnh hưởng:** FR-06/QT-06 được áp dụng cho nhật ký nạp thay vì trạng thái đơn; hoãn sang khi có nguồn trạng thái.

### TD-06 · Khoá nghiệp vụ của fact là (cửa hàng, mã đơn, số thứ tự dòng)
- **Thay đổi:** Thêm `UNIQUE(store_key, order_code, line_no)` và nạp bằng `INSERT … ON CONFLICT DO UPDATE`.
- **Vì sao:** Mã đơn trùng giữa các cửa hàng (đo được 14.302 mã đơn lặp lại); dùng `order_id` một mình sẽ gộp sai hoặc nạp trùng khi chạy lại.
- **Ảnh hưởng:** `sql/schema.sql`, `load/warehouse.py`, quy tắc CL03, test `test_chay_lai_lan_hai_khong_nhan_doi_du_lieu`.

### TD-07 · Bảng reject mở rộng + thêm `fix_log`, `quality_result`, `etl_run_log`
- **Thay đổi:** `reject_records` thêm `rule_code, field_name, raw_value, first_run_id, last_run_id` + UNIQUE; thêm 3 bảng vận hành.
- **Vì sao:** Khung 3 của wireframe BT1 cần mã quy tắc, cột lỗi, giá trị gốc và lịch sử lần chạy; UNIQUE để chạy lại không nhân đôi reject.
- **Ảnh hưởng:** Màn hình 4 “Chất lượng dữ liệu”, D3.

### TD-08 · Sai thành tiền dòng hàng được SỬA chứ không loại
- **Thay đổi:** Dòng có `thanh_tien ≠ so_luong × don_gia` (1,46%) được giữ, tính lại theo SL × đơn giá, ghi `fix_log`.
- **Vì sao:** SL và đơn giá là giá trị gốc nhập tại quầy, thành tiền là giá trị dẫn xuất; loại bỏ sẽ làm mất doanh thu thật.
- **Ảnh hưởng:** CL08, `scripts/doi_soat.py` (đối soát theo SL × đơn giá).

### TD-09 · `dim_store`, `dim_product` thêm cột
- **Thay đổi:** `dim_store`: `region` lấy từ `data/reference/vung_mien.csv`, thêm `district, open_date, is_deleted`. `dim_product`: thêm `brand, list_price, cost_ratio, source_product_id, is_deleted`.
- **Vì sao:** Cần ngày khai trương cho quy tắc CL04; `is_deleted` hiện thực QT-13 (xoá mềm); giá niêm yết để tính giảm giá.
- **Ảnh hưởng:** `sql/schema.sql`, `transform.build_dim_*`.

### TD-10 · Mặc định “Tháng này” → “Tháng gần nhất có dữ liệu”
- **Thay đổi:** UC01 bước 2 đặt mặc định tháng chứa ngày giao dịch cuối cùng trong kho (08/2026).
- **Vì sao:** Dữ liệu kết thúc 31/08/2026; “tháng này” (10/2026) luôn rỗng, người dùng mở lên sẽ tưởng hệ thống hỏng.
- **Ảnh hưởng:** `service.parse_filters`, nút “Tháng gần nhất”.

### TD-11 · Dashboard có máy chủ API thay vì tệp HTML tĩnh
- **Thay đổi:** BT1 ghi “HTML dashboard (không cần server)” → Flask API (routes/service/repository) + giao diện HTML/JS.
- **Vì sao:** Cần tách lớp (C2), cần truy vấn theo bộ lọc thật và cần trạng thái “lỗi kết nối kho” (UC01 luồng 3a) — tệp tĩnh không làm được.
- **Ảnh hưởng:** `src/serve/`, README bước 7.

### TD-12 · 3 khung wireframe → 4 màn hình
- **Thay đổi:** Tách “Kênh & thanh toán” (FR-08/09) và “Chất lượng dữ liệu” (khung 3) thành hai màn hình riêng.
- **Vì sao:** Wireframe BT1 khung 3 mô tả chất lượng dữ liệu nhưng phần chữ lại mô tả kênh & thanh toán — giữ cả hai.
- **Ảnh hưởng:** `static/js/screens.js`.

### TD-13 · Phạm vi hoãn sang BT3
- **Thay đổi:** Chưa có: lập lịch micro-batch 3 phút (NFR-02), gửi Email/Push cảnh báo (NFR-08 — FR-11 hiện chỉ hiển thị trên dashboard), xuất `.xlsx` (FR-07 hiện là CSV UTF-8 mở được bằng Excel), đăng nhập & phân quyền theo cửa hàng (QT-14 — tạm thay bằng bộ lọc cửa hàng), dự báo AI (US8 Won't).
- **Vì sao:** Đề BT2 ghi rõ không yêu cầu triển khai, giám sát, bảo mật đầy đủ; ưu tiên 4 mục cốt lõi.
- **Ảnh hưởng:** không đổi lược đồ; ghi nhận để làm ở BT3.

### TD-14 · Kiểu dữ liệu theo SQLite
- **Thay đổi:** `BIGSERIAL / VARCHAR(n) / NUMERIC(14,2) / TIMESTAMP` → `INTEGER AUTOINCREMENT / TEXT / NUMERIC / TEXT ISO-8601`.
- **Vì sao:** BT1 đã chọn SQLite (sơ đồ kiến trúc mục 3.1) nhưng bảng cột viết theo kiểu PostgreSQL.
- **Ảnh hưởng:** `sql/schema.sql`. Không dùng `customers_raw.csv` vì luồng L6 không phân tích theo khách hàng.
