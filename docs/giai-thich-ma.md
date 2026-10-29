# Chuẩn bị trả lời bộ ba câu hỏi chuẩn (Buổi 12, bước 8)

> Tài liệu ôn tập cá nhân. Với mỗi chức năng: **(1) vì sao chọn cách này · (2) dữ liệu ×10 thì hỏng đâu trước ·
> (3) dòng mã chịu trách nhiệm.** Số dòng ứng với phiên bản tag `v0.2` — mở tệp và chỉ vào đúng dòng.

## A. Chạy lại không nhân đôi (C5)
- **Dòng mã:** `src/load/warehouse.py` dòng ~107 `ON CONFLICT(store_key, order_code, line_no) DO UPDATE`; ràng buộc
  `UNIQUE (store_key, order_code, line_no)` trong `sql/schema.sql`; `line_no` sinh ở `src/transform/transform.py` dòng 127.
- **Vì sao:** UPSERT theo khoá nghiệp vụ giữ được `order_item_id` cũ và cập nhật số liệu nếu nguồn sửa. Cách “xoá rồi
  nạp lại theo batch” cũng đúng nhưng đổi khoá thay thế mỗi lần và mất dấu `loaded_at`. Không dùng `order_id` một mình
  vì mã đơn trùng giữa cửa hàng (14.302 mã lặp).
- **Test:** `tests/test_pipeline.py::test_chay_lai_lan_hai_khong_nhan_doi_du_lieu`.
- **×10 dữ liệu:** `executemany` từng dòng trong một giao dịch vẫn ổn với 350 nghìn dòng; chỗ chậm trước là
  `_rows_from_check` (lặp Python từng dòng lỗi) và `tinh_chi_so_dong_hang` gọi theo từng dòng → vector hoá bằng pandas.

## B. Đọc 3 định dạng ngày (CL01)
- **Dòng mã:** `src/transform/rules.py` dòng 17–19 (3 biểu thức chính quy), dòng 22 `parse_ngay`, khối `try: date(y, mth, d)`
  bắt ngày không tồn tại (31/02).
- **Vì sao không dùng `pd.to_datetime(dayfirst=True)`:** nó đoán định dạng, đọc “2025.12.19” và “2-6-26” không nhất quán
  và không cho biết *vì sao* hỏng; hàm tự viết trả lý do cho bảng reject.
- **Test:** `test_doc_du_ba_dinh_dang_ngay`, `test_ngay_29_thang_2_nam_nhuan_va_khong_nhuan`, `test_ngay_khong_doc_duoc_vao_bang_reject_kem_ly_do`.

## C. Hàm kiểm chất lượng trả về số đo (D2)
- **Dòng mã:** `src/quality/checks.py` lớp `CheckResult` (dòng ~27–60: `rows_checked`, `rows_failed`, `fail_rate`, `passed`),
  10 hàm `kiem_tra_*`. Tỉ lệ hợp lệ toàn lần chạy: `danh_gia_ti_le_hop_le` dòng 212, phép so sánh `rate >= threshold` dòng 217
  (đúng bằng ngưỡng 95% là ĐẠT).
- **Vì sao tách khỏi transform:** cùng một mặt nạ lỗi dùng cho cả việc loại dòng và báo cáo — một nơi duy nhất định nghĩa “lỗi”.

## D. Thành tiền dòng hàng sai → sửa, không loại (CL08)
- **Dòng mã:** `checks.kiem_tra_thanh_tien_dong_hang` (dòng 169); vòng ghi `fix_log` trong `transform.py` (khối `fixes = []`).
- **Vì sao:** số lượng & đơn giá là dữ liệu gốc; thành tiền là dẫn xuất. Loại 520 dòng sẽ làm mất ~1,5% doanh thu thật.
  Đối soát `scripts/doi_soat.py` chứng minh doanh thu kho = Σ SL × đơn giá của nguồn (lệch 0 đ).

## E. Tách lớp dashboard (C2)
- `src/serve/repository.py` — chỉ SQL (dòng 39 mở kho **chỉ đọc** `mode=ro`; tham số qua `?`, không ghép chuỗi).
- `src/serve/service.py` — không import Flask, không có SQL (xem dòng 1–10). Lỗi nghiệp vụ ném `ValidationError`.
- `src/serve/app.py` — chỉ đổi lỗi thành mã HTTP (dòng 35–50).
- **×10:** `by_product` nhóm trên toàn fact mỗi lần lọc; sẽ chậm trước → thêm bảng tổng hợp theo sản phẩm × ngày như `agg_daily_store`.

## F. Ba trạng thái giao diện
- `static/js/api.js` dòng 22 (`AbortController` — hết 10 s coi như mất kết nối) và khối `catch` đổi lỗi mạng thành thông điệp tiếng Việt.
- `static/js/app.js` dòng 50: `status !== "ok"` → `States.empty` (phân biệt `empty_filter` và `empty_warehouse`); khối `catch` → `States.error` + nút Thử lại.
- `static/js/states.js`: ba hàm `loading`, `empty`, `error`.

## G. Mốc so sánh cho mọi con số
- `service.previous_period` (dòng 105): kỳ trước cùng số ngày liền trước. KPI có `delta_pct`; biểu đồ có đường trung bình nét đứt;
  bảng cửa hàng có `vs_avg_pct`; tỉ lệ hợp lệ so với ngưỡng 95% và lần chạy trước.
