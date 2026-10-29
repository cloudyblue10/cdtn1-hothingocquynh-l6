"""Đối soát NFR-06: doanh thu trong kho phải KHỚP 0 VNĐ với doanh thu tính lại trực tiếp từ CSV nguồn.

    python scripts/doi_soat.py                 # dùng DATA_DIR và DW_PATH trong .env

Cách tính độc lập (không dùng mã transform): đọc lại CSV bằng pandas, lấy các dòng hàng thuộc
đơn KHÔNG nằm trong bảng reject, doanh thu = so_luong × don_gia; so với SUM(net_revenue) trong kho.
Chỉ đúng khi kho được nạp từ CHÍNH thư mục DATA_DIR này (không trộn bộ mẫu và bộ đầy đủ).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    items = pd.read_csv(s.data_dir / "order_items.csv", dtype=str)
    items["row_number"] = range(2, len(items) + 2)
    conn = sqlite3.connect(s.dw_path)
    rejected_rows = {r for (r,) in conn.execute(
        "SELECT DISTINCT row_number FROM reject_records WHERE source_file='order_items.csv'")}
    kept = items[~items["row_number"].isin(rejected_rows)]
    source_total = int((kept["so_luong"].astype(int) * kept["don_gia"].astype(int)).sum())
    dw_total = int(conn.execute("SELECT COALESCE(SUM(net_revenue),0) FROM fact_order_item").fetchone()[0])
    dw_rows = conn.execute("SELECT COUNT(*) FROM fact_order_item").fetchone()[0]
    conn.close()
    diff = dw_total - source_total
    print(f"Dòng hàng nguồn giữ lại : {len(kept):>14,}   | dòng fact trong kho: {dw_rows:,}")
    print(f"Doanh thu tính từ nguồn  : {source_total:>14,} đ")
    print(f"Doanh thu trong kho      : {dw_total:>14,} đ")
    print(f"Chênh lệch               : {diff:>14,} đ  → {'KHỚP (NFR-06 ĐẠT)' if diff == 0 and len(kept) == dw_rows else 'LỆCH'}")
    return 0 if diff == 0 and len(kept) == dw_rows else 1


if __name__ == "__main__":
    sys.exit(main())
