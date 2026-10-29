"""Kiểm thử ĐƠN VỊ cho hàm thuần (rules) và hàm kiểm chất lượng (checks)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.quality import checks as Q
from src.transform.rules import (parse_ngay, parse_so_nguyen_duong, parse_tien,
                                 phan_loai_thanh_toan, tinh_chi_so_dong_hang,
                                 ty_suat_loi_nhuan_gop)


# ============================================================ LOẠI 1 — LUỒNG ĐÚNG
@pytest.mark.luong_dung
@pytest.mark.parametrize("raw, expected", [
    ("17/08/2025", date(2025, 8, 17)),   # dd/mm/yyyy
    ("2-6-26", date(2026, 6, 2)),        # d-m-yy
    ("2025.12.19", date(2025, 12, 19)),  # yyyy.mm.dd
])
def test_doc_du_ba_dinh_dang_ngay(raw, expected):
    assert parse_ngay(raw) == (expected, None)


@pytest.mark.luong_dung
@pytest.mark.parametrize("raw, expected", [
    ("11990000", 11_990_000), ("11.990.000đ", 11_990_000), ("1,234,000 đ", 1_234_000),
])
def test_doc_so_tien_dang_so_va_dang_van_ban(raw, expected):
    assert parse_tien(raw) == expected


@pytest.mark.luong_dung
def test_cong_thuc_chi_so_dong_hang():
    m = tinh_chi_so_dong_hang(so_luong=2, gia_niem_yet=1000, gia_ban=900, gia_von=700)
    assert m == {"gross_amount": 2000, "discount_amount": 200, "net_revenue": 1800,
                 "cogs_amount": 1400, "gross_profit": 400}
    assert phan_loai_thanh_toan("Trả góp 0%") == "TRA_GOP"
    assert phan_loai_thanh_toan(None) == "TRA_THANG"


@pytest.mark.luong_dung
def test_moi_ham_kiem_tra_tra_ve_so_do_duoc():
    """D2: hàm kiểm chất lượng trả về số dòng kiểm, số dòng lỗi, tỉ lệ lỗi và kết luận."""
    df = pd.DataFrame({"ngay": ["01/01/2025", "xx", None, "2025.01.02"]})
    r = Q.kiem_tra_ngay_ban(df)
    assert (r.rows_checked, r.rows_failed, r.fail_rate) == (4, 2, 50.0)
    assert r.passed is False                       # 50% > ngưỡng 1%
    assert set(r.summary()) >= {"rule_code", "rows_checked", "rows_failed", "fail_rate", "passed"}


# ============================================================ LOẠI 2 — GIÁ TRỊ BIÊN
@pytest.mark.gia_tri_bien
def test_ngay_29_thang_2_nam_nhuan_va_khong_nhuan():
    assert parse_ngay("29/02/2024")[0] == date(2024, 2, 29)
    d, reason = parse_ngay("29/02/2025")
    assert d is None and "không tồn tại" in reason


@pytest.mark.gia_tri_bien
@pytest.mark.parametrize("loaded, extracted, ok", [(95, 100, True), (9499, 10000, False), (100, 100, True)])
def test_ti_le_hop_le_dung_bang_nguong_95_la_dat(loaded, extracted, ok):
    rate, passed = Q.danh_gia_ti_le_hop_le(loaded, extracted, threshold=95.0)
    assert passed is ok


@pytest.mark.gia_tri_bien
def test_ti_le_loi_dung_bang_nguong_cho_phep_van_dat():
    """CL06 ngưỡng 0,5%: 1 lỗi / 200 dòng = đúng 0,5% => ĐẠT; 2/200 = 1% => VƯỢT."""
    ok = pd.DataFrame({"so_luong": ["1"] * 199 + ["0"], "don_gia": ["100"] * 200})
    bad = pd.DataFrame({"so_luong": ["1"] * 198 + ["0", "-1"], "don_gia": ["100"] * 200})
    assert Q.kiem_tra_so_luong_don_gia(ok).fail_rate == 0.5 and Q.kiem_tra_so_luong_don_gia(ok).passed
    assert not Q.kiem_tra_so_luong_don_gia(bad).passed


@pytest.mark.gia_tri_bien
def test_ty_suat_loi_nhuan_khi_doanh_thu_bang_0():
    assert ty_suat_loi_nhuan_gop(100, 0) is None          # không chia cho 0
    assert ty_suat_loi_nhuan_gop(25, 100) == 25.0


# ============================================================ LOẠI 3 — DỮ LIỆU SAI
@pytest.mark.du_lieu_sai
@pytest.mark.parametrize("raw", ["", None, "abc", "-5000", "12a"])
def test_so_tien_sai_tra_ve_none_khong_nem_ngoai_le(raw):
    assert parse_tien(raw) is None


@pytest.mark.du_lieu_sai
@pytest.mark.parametrize("raw", ["0", "-1", "1.5", "", None, "hai"])
def test_so_luong_khong_phai_so_nguyen_duong(raw):
    assert parse_so_nguyen_duong(raw) is None


@pytest.mark.du_lieu_sai
def test_san_pham_thieu_ty_le_gia_von_bi_danh_dau_loi_kem_ly_do():
    df = pd.DataFrame({"gia_niem_yet": ["1000", "0"], "nhom_san_pham": ["Đồng hồ", "Phụ kiện"]})
    r = Q.kiem_tra_san_pham_hop_le(df, {"Phụ kiện": 0.5})
    assert r.rows_failed == 2
    assert "chưa có tỷ lệ giá vốn" in r.reasons[0]
    assert "Giá niêm yết '0'" in r.reasons[1]
