-- =====================================================================
-- Kho dữ liệu bán hàng Mekong Mobile — Luồng L6 (Track DA)
-- Lược đồ hình sao (Star Schema) theo thiết kế BT1, mục 4.
-- Mọi lệnh dùng IF NOT EXISTS => chạy lại nhiều lần không lỗi.
-- Sai lệch so với BT1 được ghi trong docs/thay-doi-thiet-ke.md.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------- DIMENSIONS
CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER PRIMARY KEY,          -- YYYYMMDD
    full_date    TEXT    NOT NULL UNIQUE,      -- ISO yyyy-mm-dd
    day_of_week  INTEGER NOT NULL,             -- 1 = Thứ Hai ... 7 = Chủ nhật
    day          INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    year         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code   TEXT    NOT NULL UNIQUE,    -- khoá nghiệp vụ
    source_product_id INTEGER NOT NULL UNIQUE, -- product_id trong products.csv
    product_name   TEXT    NOT NULL,
    brand          TEXT,
    category_name  TEXT    NOT NULL,
    list_price     NUMERIC NOT NULL,           -- giá niêm yết
    unit_cost      NUMERIC NOT NULL,           -- giá vốn đơn vị (ƯỚC TÍNH, xem thay-doi-thiet-ke.md)
    cost_ratio     NUMERIC NOT NULL,
    is_deleted     INTEGER NOT NULL DEFAULT 0, -- QT-13: xoá mềm
    updated_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_store (
    store_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    store_code   TEXT    NOT NULL UNIQUE,
    store_name   TEXT    NOT NULL,
    region       TEXT    NOT NULL,             -- vùng miền
    city         TEXT    NOT NULL,
    district     TEXT,
    open_date    TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    is_deleted   INTEGER NOT NULL DEFAULT 0,   -- QT-13: xoá mềm
    updated_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_channel (
    channel_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_code  TEXT NOT NULL UNIQUE,
    channel_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_payment (
    payment_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_code    TEXT NOT NULL UNIQUE,
    payment_method  TEXT NOT NULL
);

-- ---------------------------------------------------------- FACT
-- GRAIN: một dòng = một dòng sản phẩm trong một đơn hàng.
-- Khoá nghiệp vụ: (store_key, order_code, line_no) — mã đơn trùng giữa
-- các cửa hàng nên KHÔNG dùng một mình order_code.
CREATE TABLE IF NOT EXISTS fact_order_item (
    order_item_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code      TEXT    NOT NULL,          -- ma_don nguồn
    line_no         INTEGER NOT NULL,          -- thứ tự dòng hàng trong đơn
    source_order_id INTEGER NOT NULL,
    date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key     INTEGER NOT NULL REFERENCES dim_product(product_key),
    channel_key     INTEGER NOT NULL REFERENCES dim_channel(channel_key),
    payment_key     INTEGER NOT NULL REFERENCES dim_payment(payment_key),
    store_key       INTEGER NOT NULL REFERENCES dim_store(store_key),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_list_price NUMERIC NOT NULL,
    unit_sale_price NUMERIC NOT NULL,
    gross_amount    NUMERIC NOT NULL,          -- SL × giá niêm yết
    discount_amount NUMERIC NOT NULL,          -- SL × (giá niêm yết − giá bán)
    net_revenue     NUMERIC NOT NULL,          -- gross − discount (− hoàn trả = 0)
    cogs_amount     NUMERIC NOT NULL,          -- SL × unit_cost
    gross_profit    NUMERIC NOT NULL,          -- net − cogs
    has_vat_invoice INTEGER NOT NULL DEFAULT 0,
    run_id          TEXT    NOT NULL,
    loaded_at       TEXT    NOT NULL,
    UNIQUE (store_key, order_code, line_no)
);
CREATE INDEX IF NOT EXISTS ix_fact_date    ON fact_order_item(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_store   ON fact_order_item(store_key, date_key);
CREATE INDEX IF NOT EXISTS ix_fact_product ON fact_order_item(product_key);

-- Bảng tổng hợp sẵn theo ngày × cửa hàng (NFR-01) — dựng lại mỗi lần chạy.
CREATE TABLE IF NOT EXISTS agg_daily_store (
    date_key      INTEGER NOT NULL,
    store_key     INTEGER NOT NULL,
    order_count   INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    net_revenue   NUMERIC NOT NULL,
    cogs_amount   NUMERIC NOT NULL,
    gross_profit  NUMERIC NOT NULL,
    PRIMARY KEY (date_key, store_key)
);

-- ---------------------------------------------------------- VẬN HÀNH ETL
-- Nhật ký các lần chạy: append-only (QT-06) — không UPDATE sau khi kết thúc.
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,             -- RUNNING | SUCCESS | FAILED
    source_dir      TEXT NOT NULL,
    rows_extracted  INTEGER DEFAULT 0,
    rows_loaded     INTEGER DEFAULT 0,
    rows_rejected   INTEGER DEFAULT 0,
    rows_fixed      INTEGER DEFAULT 0,
    valid_rate      NUMERIC,
    fact_rows_after INTEGER,
    error_message   TEXT
);

-- Bảng REJECT: dòng nguồn bị LOẠI, kèm lý do viết cho người đọc.
-- UNIQUE => chạy lại không nhân đôi bản ghi reject.
CREATE TABLE IF NOT EXISTS reject_records (
    reject_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file   TEXT    NOT NULL,
    row_number    INTEGER NOT NULL,            -- số dòng trong tệp (dòng tiêu đề = 1)
    rule_code     TEXT    NOT NULL,
    field_name    TEXT,
    raw_value     TEXT,
    reason        TEXT    NOT NULL,
    raw_data      TEXT    NOT NULL,            -- JSON của cả dòng gốc
    first_run_id  TEXT    NOT NULL,
    last_run_id   TEXT    NOT NULL,
    rejected_at   TEXT    NOT NULL,
    UNIQUE (source_file, row_number, rule_code)
);

-- Dòng nguồn được GIỮ nhưng phải SỬA tự động (vd. thành tiền dòng hàng sai).
CREATE TABLE IF NOT EXISTS fix_log (
    fix_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file  TEXT    NOT NULL,
    row_number   INTEGER NOT NULL,
    rule_code    TEXT    NOT NULL,
    field_name   TEXT    NOT NULL,
    old_value    TEXT,
    new_value    TEXT,
    reason       TEXT    NOT NULL,
    last_run_id  TEXT    NOT NULL,
    UNIQUE (source_file, row_number, rule_code)
);

-- Kết quả từng hàm kiểm chất lượng ở từng lần chạy.
CREATE TABLE IF NOT EXISTS quality_result (
    run_id        TEXT    NOT NULL,
    rule_code     TEXT    NOT NULL,
    rule_name     TEXT    NOT NULL,
    source_file   TEXT    NOT NULL,
    rows_checked  INTEGER NOT NULL,
    rows_failed   INTEGER NOT NULL,
    fail_rate     NUMERIC NOT NULL,            -- %
    max_fail_rate NUMERIC NOT NULL,            -- ngưỡng cho phép (%)
    passed        INTEGER NOT NULL,
    action        TEXT    NOT NULL,            -- LOAI | SUA | GHI_NHAN
    PRIMARY KEY (run_id, rule_code)
);
