"""PHA EXTRACT — đọc tệp nguồn CSV vào DataFrame "staging".

Hợp đồng ở ranh giới extract → transform (xem docs/data-contract.md):
  * mọi cột được đọc dạng CHUỖI (dtype=str) — chưa ép kiểu ở pha này,
    để dòng hỏng không làm sập việc đọc mà được transform đưa vào bảng reject;
  * thêm 2 cột truy vết: ``_source_file`` và ``_row_number``
    (số dòng thật trong tệp, dòng tiêu đề là dòng 1);
  * tệp thiếu cột bắt buộc => ném SourceSchemaError với thông báo rõ ràng.

Lớp này KHÔNG biết gì về kho dữ liệu hay quy tắc nghiệp vụ.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Lược đồ staging tối thiểu cho từng tệp nguồn của luồng L6.
SOURCE_SCHEMAS: dict[str, list[str]] = {
    "orders_2024_2026.csv": ["order_id", "ma_don", "ma_cua_hang", "ngay",
                             "thanh_tien", "nhan_vien", "ghi_chu"],
    "order_items.csv": ["order_id", "product_id", "so_luong", "don_gia", "thanh_tien"],
    "products.csv": ["product_id", "product_code", "product_name", "thuong_hieu",
                     "nhom_san_pham", "gia_niem_yet"],
    "stores.csv": ["store_id", "store_code", "store_name", "thanh_pho",
                   "quan_huyen", "ngay_khai_truong"],
}
REFERENCE_SCHEMAS: dict[str, list[str]] = {
    "ty_le_gia_von.csv": ["nhom_san_pham", "ty_le_gia_von"],
    "vung_mien.csv": ["thanh_pho", "vung_mien"],
}
META_COLUMNS = ["_source_file", "_row_number"]


class ExtractError(Exception):
    """Lỗi đọc nguồn — thông điệp viết cho người vận hành đọc được."""


class SourceFileError(ExtractError):
    pass


class SourceSchemaError(ExtractError):
    pass


@dataclass
class ExtractResult:
    frames: dict[str, pd.DataFrame]
    row_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts[name] for name in SOURCE_SCHEMAS if name in self.row_counts)


def read_csv_as_staging(path: Path, required_columns: list[str]) -> pd.DataFrame:
    """Đọc một tệp CSV thành DataFrame staging (toàn chuỗi + cột truy vết)."""
    if not path.exists():
        raise SourceFileError(
            f"Không tìm thấy tệp nguồn '{path.name}' trong thư mục '{path.parent}'. "
            "Kiểm tra biến DATA_DIR trong tệp .env hoặc giải nén bộ dữ liệu vào đúng thư mục."
        )
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""],
                         encoding="utf-8")
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise SourceFileError(
            f"Tệp '{path.name}' không đọc được theo định dạng CSV UTF-8 ({type(exc).__name__})."
        ) from exc

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise SourceSchemaError(
            f"Tệp '{path.name}' thiếu cột bắt buộc: {', '.join(missing)}. "
            f"Các cột hiện có: {', '.join(df.columns)}."
        )
    # Bỏ khoảng trắng thừa ở đầu/cuối mọi ô chuỗi
    for col in df.columns:
        df[col] = df[col].str.strip()
    df["_source_file"] = path.name
    df["_row_number"] = range(2, len(df) + 2)  # dòng 1 là tiêu đề
    return df


def extract_all(data_dir: Path, reference_dir: Path) -> ExtractResult:
    """Đọc toàn bộ nguồn của luồng L6. Trả về các DataFrame và số dòng đã đọc."""
    frames: dict[str, pd.DataFrame] = {}
    for name, cols in SOURCE_SCHEMAS.items():
        frames[name] = read_csv_as_staging(data_dir / name, cols)
    for name, cols in REFERENCE_SCHEMAS.items():
        frames[name] = read_csv_as_staging(reference_dir / name, cols)
    return ExtractResult(frames=frames, row_counts={k: len(v) for k, v in frames.items()})
