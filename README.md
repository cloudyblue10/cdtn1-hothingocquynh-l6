# Smart CRM · Mekong Mobile — Kho dữ liệu bán hàng & báo cáo doanh thu (L6 · Track DA)

**Học phần:** Chuyên đề tốt nghiệp 1 — HK1 2026–2027 · **Bài tập 2:** Hiện thực hoá module cốt lõi · **Tag:** `v0.2`
**Sinh viên:** Hồ Thị Ngọc Quỳnh · MSSV 2374802010426 · Lớp 261_71ITGR40203_06

## 1. Hệ thống này là gì

Hệ thống đọc bốn tệp nguồn bán hàng của Mekong Mobile (đơn hàng, dòng hàng, sản phẩm, cửa hàng), làm sạch bằng
**10 hàm kiểm chất lượng** (CL01–CL10) và nạp vào một **kho dữ liệu hình sao (SQLite)** với grain *một dòng sản
phẩm trong một đơn hàng*. Dòng không dùng được đi vào bảng **`reject_records`** kèm lý do; dòng sửa được (thành tiền
dòng hàng sai) được tính lại và ghi **`fix_log`**. Pipeline chạy bằng **một lệnh**, chạy lại **không nhân đôi**
dữ liệu (UPSERT theo khoá nghiệp vụ). Một **dashboard web 4 màn hình** (tổng quan doanh thu, sản phẩm & cửa hàng,
kênh & thanh toán, chất lượng dữ liệu) đọc kho qua API, mọi con số có mốc so sánh và xử lý đủ ba trạng thái
**đang tải · rỗng · lỗi**.

## 2. Yêu cầu môi trường

| Thành phần | Phiên bản |
|---|---|
| Python | **3.11 trở lên** (đã kiểm thử trên 3.13) |
| Cơ sở dữ liệu | SQLite 3 — có sẵn trong Python, **không cần cài thêm** |
| Thư viện | khoá đúng phiên bản trong `requirements.txt` |
| Trình duyệt | Chrome / Edge / Firefox bản hiện hành (biểu đồ SVG tự viết, không cần Internet) |
| Docker (tuỳ chọn) | Docker Desktop có `docker compose` v2.24+ |

## 3. Cài đặt và chạy — mỗi bước một lệnh

> Các lệnh viết cho macOS/Linux. Trên **Windows (PowerShell)** chỉ khác ở bước 2 và 4 (ghi ngay bên dưới).

```bash
# 1. Lấy mã nguồn đúng phiên bản nộp bài
git clone --branch v0.2 https://github.com/cloudyblue10/cdtn1-hothingocquynh-l6.git && cd cdtn1-hothingocquynh-l6

# 2. Tạo môi trường ảo                       (Windows: py -3.12 -m venv .venv)
python3 -m venv .venv

# 3. Kích hoạt môi trường ảo                 (Windows: .venv\Scripts\activate)
source .venv/bin/activate

# 4. Tạo tệp cấu hình từ mẫu                  (Windows: copy .env.example .env)
cp .env.example .env

# 5. Cài thư viện đúng phiên bản đã khoá
pip install -r requirements.txt

# 6. Chạy pipeline ETL (mặc định trên bộ mẫu data/sample — 1.500 đơn, có sẵn trong repo)
python -m src.pipeline

# 7. Mở dashboard rồi vào trình duyệt: http://127.0.0.1:8000
python -m src.serve.app
```

### Chạy trên bộ dữ liệu ĐẦY ĐỦ (26.000 đơn)

Bộ đầy đủ không được commit (quy định mục 7 của README bộ dữ liệu). Tải `CDTN1_Mekong_Mobile_Dataset_Smart_CRM.zip`
từ VLU E-learning, chép 4 tệp `orders_2024_2026.csv`, `order_items.csv`, `products.csv`, `stores.csv` vào
`data/raw/`, rồi:

```bash
python -m src.pipeline --data-dir data/raw
```
(hoặc sửa `DATA_DIR=data/raw` trong `.env`). Bộ mẫu được tạo lại bằng
`python scripts/make_sample.py --raw data/raw --out data/sample --orders 1500 --seed 42` — **seed = 42**.

### Chạy bằng Docker (tuỳ chọn — 1 lệnh)

```bash
docker compose up --build          # nạp kho rồi mở dashboard tại http://localhost:8000
```

## 4. Chạy bộ kiểm thử — MỘT lệnh

```bash
python -m pytest
```
Kết quả mong đợi: **`44 passed`**. Kiểm thử tự dựng dữ liệu trong thư mục tạm (`tests/conftest.py`), không phụ thuộc
dữ liệu trên máy. Chạy riêng từng loại: `python -m pytest -m luong_dung` · `-m gia_tri_bien` · `-m du_lieu_sai`.

## 5. Kiểm tra hệ thống đã chạy đúng

| Kiểm tra | Lệnh / thao tác | Kết quả đúng |
|---|---|---|
| Pipeline chạy xong | `python -m src.pipeline` | dòng cuối in `Tỉ lệ hợp lệ: 98.73% ... → ĐẠT` (bộ mẫu) |
| **Chạy lại không nhân đôi** | chạy `python -m src.pipeline` **lần hai** | `Tổng dòng fact_order_item sau khi nạp` **giữ nguyên** (bộ mẫu: 2025; bộ đầy đủ: 35543) |
| Đối soát doanh thu = nguồn (NFR-06) | `python scripts/doi_soat.py` | `Chênh lệch: 0 đ → KHỚP` |
| API sống | mở `http://127.0.0.1:8000/api/health` | `{"status": "ok"}` |
| Trạng thái RỖNG | Màn hình 1, chọn Từ ngày `2026-09-01` → Áp dụng | thông báo *“Không tìm thấy dữ liệu giao dịch…”* + nút về tháng có dữ liệu |
| Trạng thái LỖI dữ liệu sai | chọn Từ ngày sau Đến ngày → Áp dụng | ô ngày viền đỏ, thông báo rõ ràng, nút *Thử lại* |
| Trạng thái LỖI kết nối | tắt máy chủ (Ctrl+C) rồi bấm một tab | *“Mất kết nối tới máy chủ”* + nút *Thử lại* (không màn hình trắng) |
| Báo cáo chất lượng | mở `reports/quality_report_latest.json` | đủ 10 quy tắc, số dòng lỗi, tỉ lệ, ngưỡng |

## 6. Cấu trúc thư mục

```
src/
  extract/extract.py       PHA E — đọc CSV → staging, kiểm lược đồ cột
  transform/rules.py       hàm thuần: đọc ngày 3 định dạng, đọc tiền, công thức chỉ số
  transform/transform.py   PHA T — áp quy tắc, tách sạch/reject/fix, dựng dim & fact
  quality/checks.py        10 hàm kiểm chất lượng CL01–CL10 (mỗi hàm trả về số đo)
  load/warehouse.py        PHA L — UPSERT vào SQLite trong 1 giao dịch
  pipeline.py              điểm chạy duy nhất (điều phối E → T → L)
  serve/repository.py      SQL chỉ đọc         ┐
  serve/service.py         logic dashboard     ├ tách 3 lớp, không gọi chéo ngược chiều
  serve/app.py             routes Flask (JSON) ┘
  serve/static/            giao diện: api.js (client API) · states.js (3 trạng thái) · charts.js · screens.js
sql/schema.sql             DDL kho (Star Schema + bảng vận hành ETL)
data/sample/               bộ mẫu 1.500 đơn (commit) · data/reference/ tham chiếu · data/raw/ (không commit)
scripts/                   make_sample.py (tạo bộ mẫu) · doi_soat.py (đối soát NFR-06)
tests/                     44 kiểm thử: luồng đúng · giá trị biên · dữ liệu sai
docs/                      srs.md · thay-doi-thiet-ke.md · ai-disclosure.md · architecture-thuc-te.* · data-contract.md
```

## 7. Biến môi trường

Tất cả liệt kê trong `.env.example` (DATA_DIR, REFERENCE_DIR, DW_PATH, REPORT_DIR, QUALITY_THRESHOLD, ALERT_THRESHOLD,
API_HOST, API_PORT). Hệ thống không có mật khẩu/khoá API nào; tệp `.env` thật bị chặn bởi `.gitignore`.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `Không tìm thấy tệp nguồn 'orders_2024_2026.csv'` | kiểm tra `DATA_DIR` trong `.env` trỏ đúng thư mục có 4 tệp |
| Dashboard báo *Không thể kết nối tới Kho dữ liệu* | chưa chạy bước 6 (`python -m src.pipeline`) |
| `Address already in use` ở cổng 8000 | đổi `API_PORT=8001` trong `.env` |
| `ModuleNotFoundError: src` | chạy lệnh từ **thư mục gốc** repo và dùng dạng `python -m ...` |
