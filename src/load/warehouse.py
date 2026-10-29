"""PHA LOAD — nạp kết quả transform vào kho dữ liệu SQLite (Star Schema).

Bảo đảm CHẠY LẠI KHÔNG NHÂN ĐÔI (C5):
  * dimension: INSERT ... ON CONFLICT(khoá nghiệp vụ) DO UPDATE
  * fact     : INSERT ... ON CONFLICT(store_key, order_code, line_no) DO UPDATE
  * reject   : INSERT ... ON CONFLICT(source_file, row_number, rule_code) DO UPDATE
  * bảng tổng hợp agg_daily_store: xoá rồi dựng lại TRONG CÙNG giao dịch
Toàn bộ nạp nằm trong MỘT giao dịch: lỗi giữa chừng => ROLLBACK, kho giữ nguyên trạng thái cũ.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.transform.transform import TransformResult

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def connect(dw_path: Path) -> sqlite3.Connection:
    dw_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(dw_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def _records(df: pd.DataFrame, cols: list[str]) -> list[tuple]:
    sub = df[cols].astype(object).where(df[cols].notna(), None)
    return [tuple(r) for r in sub.itertuples(index=False, name=None)]


def _upsert_dimensions(conn: sqlite3.Connection, r: TransformResult, now: str) -> None:
    conn.executemany(
        """INSERT INTO dim_store(store_code, store_name, region, city, district, open_date,
                                 is_active, is_deleted, updated_at)
           VALUES (?,?,?,?,?,?,?,0,?)
           ON CONFLICT(store_code) DO UPDATE SET
             store_name=excluded.store_name, region=excluded.region, city=excluded.city,
             district=excluded.district, open_date=excluded.open_date,
             is_active=excluded.is_active, is_deleted=0, updated_at=excluded.updated_at""",
        [row + (now,) for row in _records(r.dim_store, ["store_code", "store_name", "region", "city",
                                                         "district", "open_date", "is_active"])],
    )
    conn.executemany(
        """INSERT INTO dim_product(product_code, source_product_id, product_name, brand,
                                   category_name, list_price, unit_cost, cost_ratio, is_deleted, updated_at)
           VALUES (?,?,?,?,?,?,?,?,0,?)
           ON CONFLICT(product_code) DO UPDATE SET
             product_name=excluded.product_name, brand=excluded.brand,
             category_name=excluded.category_name, list_price=excluded.list_price,
             unit_cost=excluded.unit_cost, cost_ratio=excluded.cost_ratio,
             is_deleted=0, updated_at=excluded.updated_at""",
        [row + (now,) for row in _records(r.dim_product, ["product_code", "source_product_id",
                                                           "product_name", "brand", "category_name",
                                                           "list_price", "unit_cost", "cost_ratio"])],
    )
    # QT-13: danh mục biến mất khỏi nguồn => xoá MỀM, không DELETE
    _soft_delete(conn, "dim_store", "store_code", list(r.dim_store["store_code"]), now)
    _soft_delete(conn, "dim_product", "product_code", list(r.dim_product["product_code"]), now)

    conn.executemany(
        "INSERT INTO dim_channel(channel_code, channel_name) VALUES (?,?) "
        "ON CONFLICT(channel_code) DO UPDATE SET channel_name=excluded.channel_name",
        _records(r.dim_channel, ["channel_code", "channel_name"]))
    conn.executemany(
        "INSERT INTO dim_payment(payment_code, payment_method) VALUES (?,?) "
        "ON CONFLICT(payment_code) DO UPDATE SET payment_method=excluded.payment_method",
        _records(r.dim_payment, ["payment_code", "payment_method"]))
    conn.executemany(
        "INSERT INTO dim_date VALUES (?,?,?,?,?,?,?) ON CONFLICT(date_key) DO NOTHING",
        _records(r.dim_date, ["date_key", "full_date", "day_of_week", "day", "month", "quarter", "year"]))


def _soft_delete(conn, table: str, key: str, keep: list[str], now: str) -> None:
    if not keep:
        return
    marks = ",".join("?" * len(keep))
    conn.execute(f"UPDATE {table} SET is_deleted=1, updated_at=? "
                 f"WHERE is_deleted=0 AND {key} NOT IN ({marks})", [now, *keep])


def _key_map(conn, table: str, code_col: str, key_col: str) -> dict[str, int]:
    return dict(conn.execute(f"SELECT {code_col}, {key_col} FROM {table}").fetchall())


def _upsert_fact(conn: sqlite3.Connection, r: TransformResult, run_id: str, now: str) -> None:
    if r.fact.empty:
        return
    f = r.fact.copy()
    f["store_key"] = f["store_code"].map(_key_map(conn, "dim_store", "store_code", "store_key"))
    f["product_key"] = f["product_code"].map(_key_map(conn, "dim_product", "product_code", "product_key"))
    f["channel_key"] = f["channel_code"].map(_key_map(conn, "dim_channel", "channel_code", "channel_key"))
    f["payment_key"] = f["payment_code"].map(_key_map(conn, "dim_payment", "payment_code", "payment_key"))
    cols = ["order_code", "line_no", "source_order_id", "date_key", "product_key", "channel_key",
            "payment_key", "store_key", "quantity", "unit_list_price", "unit_sale_price",
            "gross_amount", "discount_amount", "net_revenue", "cogs_amount", "gross_profit",
            "has_vat_invoice"]
    conn.executemany(
        f"""INSERT INTO fact_order_item({",".join(cols)}, run_id, loaded_at)
            VALUES ({",".join("?" * len(cols))}, ?, ?)
            ON CONFLICT(store_key, order_code, line_no) DO UPDATE SET
              source_order_id=excluded.source_order_id, date_key=excluded.date_key,
              product_key=excluded.product_key, channel_key=excluded.channel_key,
              payment_key=excluded.payment_key, quantity=excluded.quantity,
              unit_list_price=excluded.unit_list_price, unit_sale_price=excluded.unit_sale_price,
              gross_amount=excluded.gross_amount, discount_amount=excluded.discount_amount,
              net_revenue=excluded.net_revenue, cogs_amount=excluded.cogs_amount,
              gross_profit=excluded.gross_profit, has_vat_invoice=excluded.has_vat_invoice,
              run_id=excluded.run_id, loaded_at=excluded.loaded_at""",
        [row + (run_id, now) for row in _records(f, cols)],
    )


def _upsert_rejects_and_fixes(conn, r: TransformResult, run_id: str, now: str) -> None:
    conn.executemany(
        """INSERT INTO reject_records(source_file, row_number, rule_code, field_name, raw_value,
                                      reason, raw_data, first_run_id, last_run_id, rejected_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(source_file, row_number, rule_code) DO UPDATE SET
             field_name=excluded.field_name, raw_value=excluded.raw_value, reason=excluded.reason,
             raw_data=excluded.raw_data, last_run_id=excluded.last_run_id""",
        [row + (run_id, run_id, now) for row in _records(
            r.rejects, ["source_file", "row_number", "rule_code", "field_name", "raw_value",
                        "reason", "raw_data"])],
    )
    conn.executemany(
        """INSERT INTO fix_log(source_file, row_number, rule_code, field_name, old_value, new_value,
                               reason, last_run_id)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(source_file, row_number, rule_code) DO UPDATE SET
             old_value=excluded.old_value, new_value=excluded.new_value,
             reason=excluded.reason, last_run_id=excluded.last_run_id""",
        [row + (run_id,) for row in _records(
            r.fixes, ["source_file", "row_number", "rule_code", "field_name", "old_value",
                      "new_value", "reason"])],
    )


def _insert_quality(conn, r: TransformResult, run_id: str) -> None:
    conn.executemany(
        """INSERT INTO quality_result(run_id, rule_code, rule_name, source_file, rows_checked,
               rows_failed, fail_rate, max_fail_rate, passed, action)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [(run_id, c.rule_code, c.rule_name, c.source_file, c.rows_checked, c.rows_failed,
          c.fail_rate, c.max_fail_rate, int(c.passed), c.action) for c in r.checks],
    )


def _rebuild_aggregate(conn) -> None:
    conn.execute("DELETE FROM agg_daily_store")
    conn.execute(
        """INSERT INTO agg_daily_store
           SELECT date_key, store_key, COUNT(DISTINCT order_code), SUM(quantity),
                  SUM(net_revenue), SUM(cogs_amount), SUM(gross_profit)
           FROM fact_order_item GROUP BY date_key, store_key""")


def load(conn: sqlite3.Connection, r: TransformResult, run_id: str, now: str) -> int:
    """Nạp toàn bộ trong một giao dịch. Trả về số dòng fact sau khi nạp."""
    with conn:  # BEGIN ... COMMIT, hoặc ROLLBACK nếu có ngoại lệ
        _upsert_dimensions(conn, r, now)
        _upsert_fact(conn, r, run_id, now)
        _upsert_rejects_and_fixes(conn, r, run_id, now)
        _insert_quality(conn, r, run_id)
        _rebuild_aggregate(conn)
    return conn.execute("SELECT COUNT(*) FROM fact_order_item").fetchone()[0]


def write_run_log(conn: sqlite3.Connection, run: dict) -> None:
    """Ghi MỘT dòng nhật ký cho lần chạy (append-only, ghi khi đã có kết quả cuối)."""
    cols = ["run_id", "started_at", "finished_at", "status", "source_dir", "rows_extracted",
            "rows_loaded", "rows_rejected", "rows_fixed", "valid_rate", "fact_rows_after",
            "error_message"]
    with conn:
        conn.execute(f"INSERT INTO etl_run_log({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [run.get(c) for c in cols])
