"""LỚP REPOSITORY — nơi DUY NHẤT chứa câu lệnh SQL đọc kho dữ liệu.

* Mở kho ở chế độ CHỈ ĐỌC (mode=ro): dashboard không bao giờ ghi vào kho.
* Mọi tham số truyền qua placeholder '?' — không ghép chuỗi giá trị người dùng vào SQL.
* Lỗi sqlite được đổi thành WarehouseUnavailable với thông điệp cho người dùng;
  chi tiết kỹ thuật chỉ ghi log, không trả ra giao diện.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.serve.errors import WarehouseUnavailable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Filters:
    date_from: int          # date_key YYYYMMDD
    date_to: int
    store_code: str | None = None
    category: str | None = None


class WarehouseRepository:
    def __init__(self, dw_path: Path):
        self.dw_path = Path(dw_path)

    # ------------------------------------------------------------ hạ tầng
    def _query(self, sql: str, params: list | tuple = ()) -> list[dict]:
        if not self.dw_path.exists():
            raise WarehouseUnavailable(
                "Không thể kết nối tới Kho dữ liệu.",
                "Tệp kho chưa tồn tại — hãy chạy pipeline (python -m src.pipeline) rồi bấm Thử lại.")
        try:
            conn = sqlite3.connect(f"file:{self.dw_path.as_posix()}?mode=ro", uri=True, timeout=3)
            conn.row_factory = sqlite3.Row
            try:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            log.exception("Lỗi truy vấn kho dữ liệu: %s", exc)
            raise WarehouseUnavailable(
                "Không thể kết nối tới Kho dữ liệu. Vui lòng kiểm tra đường truyền.",
                "Kho có thể đang được pipeline ghi hoặc chưa khởi tạo xong. Đợi vài giây rồi bấm Thử lại.",
            ) from exc

    @staticmethod
    def _where(f: Filters, alias: str = "f") -> tuple[str, list]:
        sql = [f"{alias}.date_key BETWEEN ? AND ?"]
        params: list = [f.date_from, f.date_to]
        if f.store_code:
            sql.append("s.store_code = ?")
            params.append(f.store_code)
        if f.category:
            sql.append("p.category_name = ?")
            params.append(f.category)
        return " AND ".join(sql), params

    _JOIN = ("FROM fact_order_item f JOIN dim_store s ON s.store_key = f.store_key "
             "JOIN dim_product p ON p.product_key = f.product_key ")

    # ------------------------------------------------------------ danh mục / meta
    def fact_count(self) -> int:
        return self._query("SELECT COUNT(*) AS n FROM fact_order_item")[0]["n"]

    def date_range(self) -> dict:
        return self._query("SELECT MIN(date_key) AS min_key, MAX(date_key) AS max_key FROM fact_order_item")[0]

    def stores(self) -> list[dict]:
        return self._query("SELECT store_code, store_name, city, region FROM dim_store "
                           "WHERE is_deleted = 0 ORDER BY store_code")

    def categories(self) -> list[str]:
        return [r["category_name"] for r in self._query(
            "SELECT DISTINCT category_name FROM dim_product WHERE is_deleted = 0 ORDER BY 1")]

    # ------------------------------------------------------------ tổng quan
    def kpis(self, f: Filters) -> dict:
        w, p = self._where(f)
        return self._query(
            f"""SELECT COALESCE(SUM(f.net_revenue),0)   AS net_revenue,
                       COUNT(DISTINCT f.store_key || '|' || f.order_code) AS orders,
                       COALESCE(SUM(f.quantity),0)       AS quantity,
                       COALESCE(SUM(f.gross_amount),0)   AS gross_amount,
                       COALESCE(SUM(f.discount_amount),0) AS discount_amount,
                       COALESCE(SUM(f.cogs_amount),0)    AS cogs_amount,
                       COALESCE(SUM(f.gross_profit),0)   AS gross_profit,
                       COUNT(*)                          AS line_count
                {self._JOIN} WHERE {w}""", p)[0]

    def daily_series(self, f: Filters) -> list[dict]:
        """Không lọc danh mục => đọc bảng tổng hợp agg_daily_store (NFR-01); có lọc => đọc fact."""
        if not f.category:
            sql = ["a.date_key BETWEEN ? AND ?"]
            params: list = [f.date_from, f.date_to]
            if f.store_code:
                sql.append("s.store_code = ?")
                params.append(f.store_code)
            return self._query(
                f"""SELECT d.full_date AS day, SUM(a.net_revenue) AS net_revenue,
                           SUM(a.order_count) AS orders
                    FROM agg_daily_store a JOIN dim_store s ON s.store_key = a.store_key
                    JOIN dim_date d ON d.date_key = a.date_key
                    WHERE {' AND '.join(sql)} GROUP BY d.full_date ORDER BY d.full_date""", params)
        w, p = self._where(f)
        return self._query(
            f"""SELECT d.full_date AS day, SUM(f.net_revenue) AS net_revenue,
                       COUNT(DISTINCT f.store_key || '|' || f.order_code) AS orders
                {self._JOIN} JOIN dim_date d ON d.date_key = f.date_key
                WHERE {w} GROUP BY d.full_date ORDER BY d.full_date""", p)

    # ------------------------------------------------------------ sản phẩm & cửa hàng
    def by_product(self, f: Filters, search: str | None, sort: str) -> list[dict]:
        w, p = self._where(f)
        if search:
            w += " AND (p.product_code LIKE ? OR p.product_name LIKE ?)"
            p += [f"%{search}%", f"%{search}%"]
        order = "quantity DESC, net_revenue DESC" if sort == "quantity" else "net_revenue DESC"
        return self._query(
            f"""SELECT p.product_code, p.product_name, p.brand, p.category_name,
                       SUM(f.quantity) AS quantity, SUM(f.net_revenue) AS net_revenue,
                       SUM(f.cogs_amount) AS cogs_amount, SUM(f.gross_profit) AS gross_profit
                {self._JOIN} WHERE {w}
                GROUP BY p.product_key ORDER BY {order} LIMIT 200""", p)

    def by_store(self, f: Filters) -> list[dict]:
        w, p = self._where(f)
        return self._query(
            f"""SELECT s.store_code, s.store_name, s.city, s.region,
                       SUM(f.net_revenue) AS net_revenue, SUM(f.gross_profit) AS gross_profit,
                       COUNT(DISTINCT f.order_code) AS orders
                {self._JOIN} WHERE {w}
                GROUP BY s.store_key ORDER BY net_revenue DESC""", p)

    def by_category(self, f: Filters) -> list[dict]:
        w, p = self._where(f)
        return self._query(
            f"""SELECT p.category_name, SUM(f.net_revenue) AS net_revenue,
                       SUM(f.gross_profit) AS gross_profit, SUM(f.quantity) AS quantity
                {self._JOIN} WHERE {w} GROUP BY p.category_name ORDER BY net_revenue DESC""", p)

    # ------------------------------------------------------------ kênh & thanh toán
    def by_payment(self, f: Filters) -> list[dict]:
        w, p = self._where(f)
        return self._query(
            f"""SELECT pm.payment_code, pm.payment_method, c.channel_name,
                       COUNT(DISTINCT f.store_key || '|' || f.order_code) AS orders,
                       SUM(f.net_revenue) AS net_revenue
                {self._JOIN} JOIN dim_payment pm ON pm.payment_key = f.payment_key
                JOIN dim_channel c ON c.channel_key = f.channel_key
                WHERE {w} GROUP BY pm.payment_code, c.channel_name ORDER BY net_revenue DESC""", p)

    def payment_monthly(self, f: Filters) -> list[dict]:
        w, p = self._where(f)
        return self._query(
            f"""SELECT substr(d.full_date,1,7) AS month, pm.payment_code,
                       SUM(f.net_revenue) AS net_revenue
                {self._JOIN} JOIN dim_payment pm ON pm.payment_key = f.payment_key
                JOIN dim_date d ON d.date_key = f.date_key
                WHERE {w} GROUP BY month, pm.payment_code ORDER BY month""", p)

    # ------------------------------------------------------------ xuất CSV
    def export_rows(self, f: Filters, limit: int = 100_000) -> list[dict]:
        w, p = self._where(f)
        return self._query(
            f"""SELECT d.full_date AS ngay, s.store_code AS ma_cua_hang, f.order_code AS ma_don,
                       p.product_code AS ma_san_pham, f.quantity AS so_luong,
                       f.net_revenue AS doanh_thu_thuan
                {self._JOIN} JOIN dim_date d ON d.date_key = f.date_key
                WHERE {w} ORDER BY d.full_date, s.store_code, f.order_code, f.line_no LIMIT ?""",
            p + [limit])

    # ------------------------------------------------------------ chất lượng & nhật ký nạp
    def runs(self, limit: int = 10) -> list[dict]:
        return self._query("SELECT * FROM etl_run_log ORDER BY started_at DESC, rowid DESC LIMIT ?", [limit])

    def quality_results(self, run_id: str) -> list[dict]:
        return self._query("SELECT * FROM quality_result WHERE run_id = ? ORDER BY rule_code", [run_id])

    def reject_counts(self) -> list[dict]:
        return self._query("SELECT rule_code, COUNT(*) AS n FROM reject_records GROUP BY rule_code ORDER BY rule_code")

    def rejects(self, rule_code: str | None, limit: int = 50) -> list[dict]:
        if rule_code:
            return self._query("SELECT source_file, row_number, rule_code, field_name, raw_value, reason "
                               "FROM reject_records WHERE rule_code = ? ORDER BY rule_code, row_number LIMIT ?",
                               [rule_code, limit])
        return self._query("SELECT source_file, row_number, rule_code, field_name, raw_value, reason "
                           "FROM reject_records ORDER BY rule_code, row_number LIMIT ?", [limit])

    def fix_count(self) -> int:
        return self._query("SELECT COUNT(*) AS n FROM fix_log")[0]["n"]
