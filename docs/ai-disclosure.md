# Bảng khai báo sử dụng công cụ AI — Bài tập 2

> Cập nhật từ bảng khai báo BT1. Theo chính sách liêm chính AI của học phần: em được dùng AI để học khái niệm, gợi ý
> cách viết, tìm nguyên nhân lỗi, rà soát mã — với điều kiện **khai báo cụ thể** và **hiểu mọi dòng mã đã nộp**.
> Cột cuối ghi cách em đã kiểm chứng phần do AI sinh ra.

| Công cụ | Dùng vào việc gì | Áp dụng ở tệp / hàm nào | Em đã kiểm chứng thế nào |
|---|---|---|---|
| Claude (Anthropic) | Sinh bản nháp mã pipeline ETL theo thiết kế Star Schema của BT1: đọc CSV, 10 hàm kiểm chất lượng, nạp UPSERT | `src/extract/extract.py`, `src/quality/checks.py`, `src/transform/*.py`, `src/load/warehouse.py`, `src/pipeline.py` | Chạy `python -m src.pipeline` hai lần trên bộ đầy đủ: fact giữ 35.543 dòng cả hai lần; đối chiếu tỉ lệ lỗi đo được (ngày trống 0,44%, thành tiền dòng sai 1,46%, tổng tiền đơn dạng văn bản/trống 1,89%) với bảng mục 3 README bộ dữ liệu; chạy `scripts/doi_soat.py` ra chênh lệch 0 đ |
| Claude (Anthropic) | Gợi ý hàm đọc ngày 3 định dạng và đọc số tiền dạng văn bản | `src/transform/rules.py` — `parse_ngay`, `parse_tien` | Test tham số hoá cho cả 3 định dạng, ngày 29/02 năm nhuận/không nhuận, chuỗi “abc”, số âm (`tests/test_rules_quality.py`) |
| Claude (Anthropic) | Sinh bản nháp API Flask tách routes / service / repository và giao diện 4 màn hình có 3 trạng thái, biểu đồ SVG | `src/serve/*.py`, `src/serve/static/**` | Mở tệp `service.py` kiểm tra không import Flask, không có SQL; tắt máy chủ khi đang mở giao diện để thấy trạng thái lỗi; chọn tháng 09/2026 để thấy trạng thái rỗng; so số KPI tháng 08/2026 với truy vấn SQL tay |
| Claude (Anthropic) | Gợi ý bộ kiểm thử ba loại và dữ liệu mini tự dựng | `tests/conftest.py`, `tests/test_*.py` | Chạy `python -m pytest` → 44 passed; cố ý sửa sai công thức giảm giá để thấy test `test_chi_so_tai_chinh_dung_cong_thuc_bt1` FAIL rồi hoàn tác |
| Claude (Anthropic) | Soạn nháp README, `thay-doi-thiet-ke.md`, `data-contract.md`, sơ đồ kiến trúc Mermaid | `README.md`, `docs/*` | Làm phép thử “thư mục trống” ở mục 2.4 đề bài: clone vào thư mục mới, làm đúng từng lệnh README, không thêm lệnh nào |
| — không dùng — | Quyết định thiết kế: grain, khoá nghiệp vụ (cửa hàng + mã đơn), ngưỡng CL01–CL10, chọn sửa thay vì loại cho CL08, tỷ lệ giá vốn giả định | `docs/thay-doi-thiet-ke.md`, `data/reference/ty_le_gia_von.csv` | Không áp dụng |

**Lưu ý trung thực (em tự kiểm trước khi nộp):** các con số ở cột cuối là kết quả chạy thật trên bộ dữ liệu của học phần.
Em đã đọc từng tệp ở cột thứ ba và chuẩn bị trả lời bộ ba câu hỏi chuẩn (xem `docs/giai-thich-ma.md`).

**Cam kết:** Tôi xác nhận đã đọc, hiểu và chịu trách nhiệm về toàn bộ nội dung nộp.
Hồ Thị Ngọc Quỳnh — MSSV 2374802010426
