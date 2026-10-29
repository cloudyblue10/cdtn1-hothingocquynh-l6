# Hợp đồng dữ liệu ở các ranh giới (Buổi 9)

## 1. Extract → Transform: lược đồ staging
| Tệp | Cột bắt buộc | Kiểu ở staging |
|---|---|---|
| orders_2024_2026.csv | order_id, ma_don, ma_cua_hang, ngay, thanh_tien, nhan_vien, ghi_chu | chuỗi |
| order_items.csv | order_id, product_id, so_luong, don_gia, thanh_tien | chuỗi |
| products.csv | product_id, product_code, product_name, thuong_hieu, nhom_san_pham, gia_niem_yet | chuỗi |
| stores.csv | store_id, store_code, store_name, thanh_pho, quan_huyen, ngay_khai_truong | chuỗi |

* Mọi DataFrame staging có thêm `_source_file` và `_row_number` (dòng tiêu đề = 1).
* Thiếu cột → `SourceSchemaError` nêu tên cột thiếu; pipeline dừng, kho giữ nguyên, `etl_run_log` ghi FAILED.
* Ô trống → `NaN` (không đổi thành 0).

## 2. Transform → Load: bảng fact
Đúng tên và thứ tự `FACT_COLUMNS` trong `src/transform/transform.py`. Tiền là số VND (float, làm tròn 2 chữ số);
`date_key` = YYYYMMDD; `payment_code` ∈ {TRA_GOP, TRA_THANG}; `channel_code` = POS.

## 3. API → Giao diện
Mọi phản hồi thành công có `status` ∈ {`ok`, `empty_filter`, `empty_warehouse`}, `filter` (khoảng đang xem) và `source`
(bảng nguồn, mã lần nạp, thời điểm nạp). Phản hồi lỗi luôn có dạng:
```json
{"error": {"code": "INVALID_FILTER | DW_UNAVAILABLE | INTERNAL", "message": "chuyện gì", "hint": "làm gì tiếp", "field": "from", "ref": "7F3A21"}}
```
Mã HTTP: 400 bộ lọc sai · 503 không mở được kho · 500 lỗi không lường trước (chi tiết chỉ ghi log, trả mã tra cứu).
Test hợp đồng: `tests/test_service_api.py::test_api_tong_quan_tra_dung_hop_dong`.
