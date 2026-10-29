"""Dữ liệu kiểm thử TỰ DỰNG trong thư mục tạm — không phụ thuộc dữ liệu có sẵn trên máy.

Bộ nguồn mini: 2 cửa hàng, 3 sản phẩm, 4 đơn hàng (đủ 3 định dạng ngày), 5 dòng hàng.
Mỗi test có thể ghi đè từng tệp để tạo tình huống sai.
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

import pytest

TODAY = date(2026, 10, 1)   # cố định "hôm nay" để test không đổi kết quả theo ngày chạy

STORES = [
    ["store_id", "store_code", "store_name", "thanh_pho", "quan_huyen", "ngay_khai_truong"],
    [1, "MM001", "Mekong Mobile Quận 1", "TP. Hồ Chí Minh", "Quận 1", "2020-04-30"],
    [2, "MM002", "Mekong Mobile Ninh Kiều", "Cần Thơ", "Ninh Kiều", "2024-07-10"],
]
PRODUCTS = [
    ["product_id", "product_code", "product_name", "thuong_hieu", "nhom_san_pham", "gia_niem_yet", "warranty_months"],
    [1, "SS0001", "Samsung Y2", "Samsung", "Điện thoại phổ thông", 2000000, 12],
    [2, "AP0002", "Apple Pro 16", "Apple", "Điện thoại cao cấp", 30000000, 12],
    [3, "XM0003", "Xiaomi Tai nghe", "Xiaomi", "Phụ kiện", 500000, 6],
]
ORDERS = [
    ["order_id", "ma_don", "ma_cua_hang", "ngay", "ten_khach", "so_dien_thoai", "thanh_tien", "nhan_vien", "ghi_chu"],
    [1, "HD00001", "MM001", "17/08/2025", "An", "0901234567", "2000000", "Anh Trung", ""],
    [2, "HD00001", "MM002", "2-6-26", "Bình", "0901234568", "31.000.000đ", "Chị Vy", "Trả góp 0%"],  # trùng mã đơn KHÁC cửa hàng: hợp lệ
    [3, "MM001-0002", "MM001", "2025.12.19", "Chi", "", "", "", "Đã xuất hóa đơn VAT"],
    [4, "HD00002", "MM002", "01/08/2026", "Dũng", "0901234569", "1800000", "Anh Huy", ""],
]
ITEMS = [
    ["order_id", "product_id", "so_luong", "don_gia", "thanh_tien"],
    [1, 1, 1, 2000000, 2000000],
    [2, 2, 1, 30000000, 30000000],
    [2, 3, 2, 500000, 1000000],
    [3, 1, 1, 1800000, 1800000],   # bán dưới giá niêm yết => giảm giá 200.000
    [4, 1, 1, 1800000, 1800000],
]
COST_RATIO = [
    ["nhom_san_pham", "ty_le_gia_von", "ghi_chu"],
    ["Điện thoại phổ thông", 0.8, ""], ["Điện thoại cao cấp", 0.85, ""], ["Phụ kiện", 0.5, ""],
]
REGIONS = [["thanh_pho", "vung_mien"], ["TP. Hồ Chí Minh", "Đông Nam Bộ"], ["Cần Thơ", "ĐBSCL"]]


def write_csv(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """Tạo thư mục nguồn + tham chiếu + đường dẫn kho tạm. Trả về dict đường dẫn."""
    src, ref = tmp_path / "src_data", tmp_path / "ref"
    src.mkdir()
    ref.mkdir()
    write_csv(src / "stores.csv", STORES)
    write_csv(src / "products.csv", PRODUCTS)
    write_csv(src / "orders_2024_2026.csv", ORDERS)
    write_csv(src / "order_items.csv", ITEMS)
    write_csv(ref / "ty_le_gia_von.csv", COST_RATIO)
    write_csv(ref / "vung_mien.csv", REGIONS)
    return {"data_dir": src, "reference_dir": ref, "dw_path": tmp_path / "dw.sqlite",
            "report_dir": tmp_path / "reports"}


@pytest.fixture
def run(workspace):
    """Hàm chạy pipeline trên workspace tạm (không in ra màn hình)."""
    from src.pipeline import run_pipeline

    def _run():
        return run_pipeline(data_dir=workspace["data_dir"], dw_path=workspace["dw_path"],
                            report_dir=workspace["report_dir"], reference_dir=workspace["reference_dir"],
                            today=TODAY, verbose=False)
    return _run


def query(dw_path: Path, sql: str, params=()):
    conn = sqlite3.connect(dw_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()
