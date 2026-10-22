# Mekong Mobile – Kho dữ liệu bán hàng & Báo cáo doanh thu

**Track:** Data Analytics (DA)  
**Luồng nghiệp vụ:** L6 – Kho dữ liệu bán hàng và báo cáo doanh thu  
**Sinh viên:** Hồ Thị Ngọc Quỳnh – MSSV 2374802010426  
**Tag:** `v0.2`

## 1. Hệ thống làm gì?

Pipeline ETL trích xuất dữ liệu đơn hàng từ 24 cửa hàng Mekong Mobile, làm sạch & chuẩn hóa (ngày, tiền, số lượng), kiểm tra chất lượng (≥ 5 rule), nạp vào kho dữ liệu mô hình star schema (dim_store, dim_product, dim_date, fact_sales), và sinh dashboard doanh thu theo tháng / theo cửa hàng.

## 2. Yêu cầu môi trường

- Python 3.10+
- pip
- (Tùy chọn) PostgreSQL 14+ nếu không dùng SQLite

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Các bước dựng hệ thống (mỗi bước một lệnh)

```bash
# 1. Cài phụ thuộc
pip install -r requirements.txt

# 2. Sao chép cấu hình
cp .env.example .env

# 3. Chạy pipeline (dùng sample ~500 đơn)
python scripts/run_pipeline.py

# 4. Chạy kiểm thử
pytest tests/ -v

# 5. Sinh dashboard
python scripts/build_dashboard.py
```

Dùng bộ đầy đủ (cần đặt file CSV vào `data/raw/`):

```bash
python scripts/run_pipeline.py --full
```

## 4. Lệnh chạy kiểm thử

```bash
pytest tests/ -v
```

Phải PASS toàn bộ. Kiểm thử tự dựng dữ liệu từ `data/sample/`, không phụ thuộc máy local.

## 5. Cách kiểm tra hệ thống đã chạy đúng

- File `data/warehouse.db` được tạo.
- `output/pipeline_summary.json` có số dòng fact > 0.
- `output/dashboard_revenue.png` có 2 biểu đồ.
- `data/reject/*.csv` chứa các dòng lỗi kèm lý do.
- Chạy lại `python scripts/run_pipeline.py` lần 2 → số dòng fact_sales không đổi (không nhân đôi).

## 6. Trạng thái hiện tại (BT2)

- [x] Pipeline extract / transform / load tách 3 thư mục
- [x] ≥ 5 hàm kiểm chất lượng
- [x] Bảng reject + quality_report
- [x] Star schema: dim_store, dim_product, dim_date, fact_sales
- [x] ≥ 3 unit test (luồng đúng · giá trị biên · dữ liệu sai)
- [x] Dashboard ≥ 2 biểu đồ có mốc tham chiếu & ghi nguồn
- [x] Chạy lại lần 2 không nhân đôi
- [ ] Triển khai PostgreSQL production (dự phòng SQLite)

## 7. Cấu trúc thư mục

```
src/
  extract/      # đọc CSV
  transform/    # làm sạch, chuẩn hóa, build dim/fact
  quality/      # ≥ 5 kiểm tra chất lượng
  load/         # ghi kho dữ liệu
scripts/
  run_pipeline.py
  build_dashboard.py
tests/
data/
  sample/       # dữ liệu mẫu (commit)
  reject/       # dòng lỗi (runtime)
  raw/          # bộ đầy đủ (không commit)
docs/
sql/
output/
```

## 8. Dữ liệu

- Sample: `data/sample/` (đã commit)
- Full: tải bộ Mekong Mobile Dataset, đặt vào `data/raw/`, chạy `--full`
- **Không commit** file CSV lớn vào Git.


## Dashboard web



## Dashboard web

```bash
python scripts/dashboard_app.py
# Mo trinh duyet: http://127.0.0.1:8050
# Hoac mo file offline: output/dashboard.html
```


Repo BT1: https://github.com/cloudyblue10/smart-crm
Schema: fact_order_item + dim_date/product/store/channel/payment (theo BT1).
