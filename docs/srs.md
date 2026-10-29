# SRS rút gọn — Luồng L6: Kho dữ liệu bán hàng và báo cáo doanh thu (từ BT1)

Trạng thái hiện thực ở BT2 ghi ở cột cuối. Sai lệch chi tiết: `docs/thay-doi-thiet-ke.md`.

## Bên liên quan
Quản lý cửa hàng · Ban giám đốc · Kế toán viên · Data Analyst · Hệ thống nguồn.

## User Story & yêu cầu chức năng

| US | Ưu tiên | UC | FR | Nội dung | BT2 |
|---|---|---|---|---|---|
| US1 | Must | UC01 | FR-01, FR-02 | KPI doanh thu, số đơn, AOV, LN gộp + xu hướng theo ngày | ✅ Màn hình 1 |
| US2 | Must | UC02 | FR-03, FR-04 | Báo cáo sản phẩm, lọc danh mục, sắp xếp, Top 10 tô màu | ✅ Màn hình 2 |
| US3 | Must | UC03 | FR-05, FR-06 | Đồng bộ đơn vào kho, lưu lịch sử | ✅ Pipeline ETL (1 kênh POS — TD-01; lịch sử = etl_run_log — TD-05) |
| US4 | Must | UC04 | FR-07 | Xuất báo cáo | ✅ CSV 6 trường (xlsx hoãn — TD-13) |
| US5 | Must | UC05 | FR-08, FR-09 | Kênh bán & phương thức thanh toán | ⚠️ Màn hình 3 (dữ liệu hạn chế — TD-01, TD-02) |
| US6 | Must | UC06 | FR-10 | COGS & LN gộp | ✅ ước tính (TD-03) |
| US7 | Should | UC07 | FR-11 | Cảnh báo biến động > 30% | ✅ hiển thị trên dashboard (chưa gửi email — TD-13) |
| US8 | Won't | — | FR-12 | Dự báo AI | ⏸ hoãn |

## Yêu cầu phi chức năng (đo ở BT2)
- NFR-01 Dashboard ≤ 3 s: bảng tổng hợp `agg_daily_store` + chỉ mục; mỗi API trả về < 0,2 s trên 35.543 dòng fact.
- NFR-06 Sai lệch doanh thu = 0 VNĐ: `scripts/doi_soat.py` → chênh lệch 0 đ.
- NFR-02, 03, 05, 07, 08: thuộc BT3 / triển khai.

## Quy tắc nghiệp vụ
- QT-06 Log append-only: `etl_run_log` chỉ INSERT.
- QT-13 Không hard-delete danh mục: `dim_store.is_deleted`, `dim_product.is_deleted`.
- QT-14 Phân quyền theo cửa hàng: hoãn (TD-13).
- Công thức: Doanh thu thuần = Tổng tiền bán − Giảm giá − Hoàn trả · AOV = DT thuần / Số đơn · COGS = Σ(SL × giá vốn) ·
  LN gộp = DT thuần − COGS · Tỷ suất LN gộp = LN gộp / DT thuần × 100.

## Grain
Một dòng `fact_order_item` = một dòng sản phẩm trong một đơn hàng.
