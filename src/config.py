"""Cấu hình hệ thống — MỌI giá trị đều đọc từ biến môi trường (.env).

Không ghi cứng đường dẫn tuyệt đối hay ngưỡng nghiệp vụ trong mã.
Danh sách đầy đủ các biến nằm trong .env.example.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv là tuỳ chọn: không có .env thì dùng giá trị mặc định
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else ROOT / p


@dataclass(frozen=True)
class Settings:
    data_dir: Path            # thư mục chứa 4 tệp nguồn CSV
    reference_dir: Path       # thư mục dữ liệu tham chiếu (tỷ lệ giá vốn)
    dw_path: Path             # tệp SQLite của kho dữ liệu
    report_dir: Path          # nơi ghi báo cáo chất lượng JSON
    quality_threshold: float  # ngưỡng tỉ lệ hợp lệ tối thiểu (%), mặc định 95
    alert_threshold: float    # ngưỡng cảnh báo biến động doanh thu ngày (%), mặc định 30
    api_host: str
    api_port: int


def get_settings() -> Settings:
    return Settings(
        data_dir=_path("DATA_DIR", "data/sample"),
        reference_dir=_path("REFERENCE_DIR", "data/reference"),
        dw_path=_path("DW_PATH", "warehouse/dw_mekong.sqlite"),
        report_dir=_path("REPORT_DIR", "reports"),
        quality_threshold=float(os.getenv("QUALITY_THRESHOLD", "95")),
        alert_threshold=float(os.getenv("ALERT_THRESHOLD", "30")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
    )
