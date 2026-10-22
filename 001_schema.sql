-- Schema kho dữ liệu Mekong Mobile (tham chiếu)
-- Runtime dùng SQLAlchemy DDL trong src/load/load_warehouse.py

CREATE TABLE IF NOT EXISTS dim_store (
    sk_store INTEGER PRIMARY KEY,
    store_id INTEGER,
    store_code TEXT UNIQUE NOT NULL,
    store_name TEXT,
    thanh_pho TEXT,
    quan_huyen TEXT,
    ngay_khai_truong TEXT
);

CREATE TABLE IF NOT EXISTS dim_product (
    sk_product INTEGER PRIMARY KEY,
    product_id INTEGER,
    product_code TEXT UNIQUE NOT NULL,
    product_name TEXT,
    thuong_hieu TEXT,
    nhom_san_pham TEXT,
    gia_niem_yet REAL,
    warranty_months INTEGER
);

CREATE TABLE IF NOT EXISTS dim_date (
    sk_date INTEGER PRIMARY KEY,
    full_date TEXT UNIQUE NOT NULL,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name TEXT,
    day INTEGER,
    day_of_week INTEGER,
    is_weekend INTEGER
);

CREATE TABLE IF NOT EXISTS fact_sales (
    fact_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    ma_don TEXT,
    sk_store INTEGER REFERENCES dim_store(sk_store),
    sk_product INTEGER REFERENCES dim_product(sk_product),
    sk_date INTEGER REFERENCES dim_date(sk_date),
    so_luong INTEGER,
    don_gia REAL,
    thanh_tien REAL
);

CREATE TABLE IF NOT EXISTS reject_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT,
    record_key TEXT,
    ly_do TEXT,
    source_file TEXT,
    loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quality_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT,
    total_rows INTEGER,
    error_rows INTEGER,
    error_rate REAL,
    detail TEXT,
    run_at TEXT DEFAULT CURRENT_TIMESTAMP
);
