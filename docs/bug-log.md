# Bug Log (bắt đầu từ BT2 — chuẩn bị cho BT3)

### BUG-001 · Major — Pipeline dừng khi ghi bảng reject
1. **Mã & mức độ:** BUG-001 · Major — pipeline không nạp được gì trên bộ đầy đủ.
2. **Phát hiện bởi:** chạy thử `python -m src.pipeline --data-dir data/raw` lần đầu.
3. **Triệu chứng:** `[LỖI] Pipeline dừng ... Object of type int64 is not JSON serializable`; `etl_run_log` ghi FAILED.
4. **Khoanh vùng:** lỗi xảy ra sau TRANSFORM, trước LOAD → ở hàm `_raw_json` (chuyển dòng gốc thành JSON cho `raw_data`).
5. **Nguyên nhân gốc:** cột kỹ thuật `line_no` (kiểu int64 của numpy) bị đưa vào JSON cùng các cột nguồn.
6. **Sửa:** loại `line_no` khỏi `raw_data` (thêm vào danh sách `META`) và `json.dumps(..., default=str)` để không sập vì kiểu lạ.
7. **Xác nhận:** chạy lại 2 lần → SUCCESS, 268 dòng reject; test `test_ngay_khong_doc_duoc_vao_bang_reject_kem_ly_do` kiểm `raw_data` đọc lại được.

### BUG-002 · Minor — Biểu đồ co chữ quá nhỏ / quá to
1. **Mã & mức độ:** BUG-002 · Minor.
2. **Phát hiện bởi:** xem dashboard ở màn hình 1360 px.
3. **Triệu chứng:** nhãn trục ở biểu đồ nửa khung còn ~6 px, ở biểu đồ toàn khung phóng to ~18 px; xuất hiện một chấm thừa ở góc trái.
4. **Khoanh vùng:** `charts.js` — SVG dùng `viewBox` cố định 760 px rồi co giãn theo khung.
5. **Nguyên nhân gốc:** kích thước vẽ không theo bề rộng thật; con trỏ hover đặt ở toạ độ âm nhưng vẫn hiển thị.
6. **Sửa:** vẽ theo `el.clientWidth`, vẽ lại khi đổi kích thước cửa sổ; con trỏ dùng `visibility="hidden"`.
7. **Xác nhận:** chụp lại 4 màn hình, chữ trục 11 px ở mọi khung.
