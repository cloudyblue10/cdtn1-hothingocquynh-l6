"""Quy tắc chuẩn hoá & công thức chỉ số — HÀM THUẦN (không đọc tệp, không chạm CSDL).

Vì là hàm thuần nên kiểm thử được bằng một dòng dữ liệu tự dựng (tests/test_rules.py).
Công thức bám mục 1.5 và 4.12 của BT1:
    Doanh thu gộp   = SL × giá niêm yết
    Giảm giá        = SL × (giá niêm yết − giá bán thực tế)
    Doanh thu thuần = Doanh thu gộp − Giảm giá − Hoàn trả   (nguồn không có hoàn trả => 0)
    COGS            = SL × giá vốn đơn vị
    Lợi nhuận gộp   = Doanh thu thuần − COGS
"""
from __future__ import annotations

import re
from datetime import date

# Ba định dạng ngày xuất hiện trong orders_2024_2026.csv (đã đo: 62% / 24% / 14%)
_RE_DMY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")      # 17/08/2025
_RE_DMY_SHORT = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{2})$")  # 2-6-26
_RE_YMD_DOT = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$")  # 2025.12.19


def parse_ngay(value: str | None) -> tuple[date | None, str | None]:
    """Đọc ngày bán từ 3 định dạng. Trả về (ngày, None) hoặc (None, lý do lỗi)."""
    if value is None or str(value).strip() == "" or str(value).lower() == "nan":
        return None, "Ngày bán để trống"
    s = str(value).strip()
    if m := _RE_DMY.match(s):
        d, mth, y = int(m[1]), int(m[2]), int(m[3])
    elif m := _RE_DMY_SHORT.match(s):
        d, mth, y = int(m[1]), int(m[2]), 2000 + int(m[3])
    elif m := _RE_YMD_DOT.match(s):
        y, mth, d = int(m[1]), int(m[2]), int(m[3])
    else:
        return None, f"Ngày bán '{s}' không thuộc định dạng nào được hỗ trợ (dd/mm/yyyy, d-m-yy, yyyy.mm.dd)"
    try:
        return date(y, mth, d), None
    except ValueError:
        return None, f"Ngày bán '{s}' không tồn tại trên lịch"


def parse_tien(value: str | None) -> int | None:
    """Đọc số tiền VND: '11990000', '11.990.000đ', '11,990,000 đ' => 11990000.

    Trả về None nếu trống hoặc không phải số tiền hợp lệ (âm, chứa chữ...).
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("", "nan"):
        return None
    s = s.replace("vnđ", "").replace("vnd", "").replace("đ", "").replace(" ", "")
    s = s.replace(".", "").replace(",", "")
    if not s.isdigit():
        return None
    return int(s)


def la_dang_van_ban(value: str | None) -> bool:
    """True nếu số tiền được ghi dạng văn bản (có 'đ' hoặc dấu phân cách)."""
    if value is None:
        return False
    s = str(value)
    return any(ch in s for ch in ("đ", ".", ",", " "))


def parse_so_nguyen_duong(value: str | None) -> int | None:
    """'2' => 2; '0', '-1', '1.5', 'abc', '' => None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s.isdigit():
        return None
    n = int(s)
    return n if n > 0 else None


def phan_loai_thanh_toan(ghi_chu: str | None) -> str:
    """Suy ra phương thức thanh toán từ ghi chú đơn (nguồn không có cột riêng).

    'Trả góp 0%' => TRA_GOP; còn lại => TRA_THANG (thanh toán một lần tại quầy).
    """
    if ghi_chu and "trả góp" in str(ghi_chu).lower():
        return "TRA_GOP"
    return "TRA_THANG"


def co_hoa_don_vat(ghi_chu: str | None) -> bool:
    return bool(ghi_chu) and "hóa đơn vat" in str(ghi_chu).lower()


def tinh_chi_so_dong_hang(so_luong: int, gia_niem_yet: float, gia_ban: float,
                          gia_von: float, hoan_tra: float = 0.0) -> dict[str, float]:
    """Tính các chỉ số tài chính của MỘT dòng hàng (grain của fact_order_item)."""
    # Giá bán cao hơn niêm yết (hiếm) => lấy giá bán làm "gộp", giảm giá = 0, không để giảm giá âm
    gross = so_luong * max(gia_niem_yet, gia_ban)
    discount = so_luong * max(gia_niem_yet - gia_ban, 0.0)
    net = gross - discount - hoan_tra          # luôn bằng SL × giá bán − hoàn trả
    cogs = so_luong * gia_von
    return {
        "gross_amount": round(gross, 2),
        "discount_amount": round(discount, 2),
        "net_revenue": round(net, 2),
        "cogs_amount": round(cogs, 2),
        "gross_profit": round(net - cogs, 2),
    }


def ty_suat_loi_nhuan_gop(loi_nhuan_gop: float, doanh_thu_thuan: float) -> float | None:
    """(LN gộp / DT thuần) × 100. Doanh thu thuần = 0 => None (không chia cho 0)."""
    if not doanh_thu_thuan:
        return None
    return round(loi_nhuan_gop / doanh_thu_thuan * 100, 2)


def date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day
