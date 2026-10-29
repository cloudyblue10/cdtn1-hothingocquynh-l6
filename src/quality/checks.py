"""Các HÀM KIỂM CHẤT LƯỢNG dữ liệu (CL01–CL10).

Mỗi hàm:
  * nhận DataFrame staging (và dữ liệu tham chiếu nếu cần),
  * KHÔNG sửa dữ liệu đầu vào,
  * trả về một CheckResult chứa SỐ ĐO ĐƯỢC: số dòng kiểm, số dòng lỗi, tỉ lệ lỗi (%),
    ngưỡng cho phép và kết luận đạt/không đạt; kèm mặt nạ dòng lỗi + lý do từng dòng
    để pha transform đưa vào bảng reject (LOAI) hoặc fix_log (SUA).

action:
  LOAI     — dòng bị loại khỏi kho, ghi vào reject_records
  SUA      — dòng được giữ, giá trị được sửa theo quy tắc, ghi vào fix_log
  GHI_NHAN — chỉ đo và báo cáo, không ảnh hưởng dữ liệu nạp
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.transform.rules import (la_dang_van_ban, parse_ngay, parse_so_nguyen_duong,
                                 parse_tien)


@dataclass
class CheckResult:
    rule_code: str
    rule_name: str
    source_file: str
    action: str
    field_name: str
    max_fail_rate: float                       # % lỗi tối đa cho phép
    failed_mask: pd.Series = field(repr=False)  # True = dòng lỗi
    reasons: pd.Series = field(repr=False)      # lý do (chỉ có nghĩa ở dòng lỗi)

    @property
    def rows_checked(self) -> int:
        return int(len(self.failed_mask))

    @property
    def rows_failed(self) -> int:
        return int(self.failed_mask.sum())

    @property
    def fail_rate(self) -> float:
        return round(self.rows_failed / self.rows_checked * 100, 3) if self.rows_checked else 0.0

    @property
    def passed(self) -> bool:
        return self.fail_rate <= self.max_fail_rate

    def summary(self) -> dict:
        return {
            "rule_code": self.rule_code, "rule_name": self.rule_name,
            "source_file": self.source_file, "field_name": self.field_name,
            "action": self.action, "rows_checked": self.rows_checked,
            "rows_failed": self.rows_failed, "fail_rate": self.fail_rate,
            "max_fail_rate": self.max_fail_rate, "passed": self.passed,
        }


def _result(code, name, src, action, field_name, max_rate, mask, reasons) -> CheckResult:
    mask = mask.fillna(False).astype(bool)
    reasons = reasons.where(mask, "")
    return CheckResult(code, name, src, action, field_name, max_rate, mask, reasons)


# ------------------------------------------------------------------ ĐƠN HÀNG
def kiem_tra_ngay_ban(orders: pd.DataFrame) -> CheckResult:
    """CL01 — Ngày bán phải đọc được theo 1 trong 3 định dạng và tồn tại trên lịch."""
    parsed = orders["ngay"].map(parse_ngay)
    reasons = parsed.map(lambda t: t[1] or "")
    mask = parsed.map(lambda t: t[0] is None)
    return _result("CL01", "Ngày bán hợp lệ", "orders_2024_2026.csv", "LOAI", "ngay",
                   1.0, mask, reasons)


def kiem_tra_ma_cua_hang(orders: pd.DataFrame, stores: pd.DataFrame) -> CheckResult:
    """CL02 — Mã cửa hàng của đơn phải có trong danh mục stores.csv."""
    known = set(stores["store_code"].dropna())
    mask = ~orders["ma_cua_hang"].isin(known)
    reasons = "Mã cửa hàng '" + orders["ma_cua_hang"].fillna("(trống)") + "' không có trong danh mục cửa hàng"
    return _result("CL02", "Mã cửa hàng tồn tại", "orders_2024_2026.csv", "LOAI",
                   "ma_cua_hang", 0.0, mask, reasons)


def kiem_tra_trung_khoa_don(orders: pd.DataFrame) -> CheckResult:
    """CL03 — Khoá nghiệp vụ (mã cửa hàng + mã đơn) không được trùng.

    Mã đơn một mình CÓ trùng giữa các cửa hàng (hợp lệ); chỉ trùng cả cặp mới là lỗi.
    Giữ bản ghi xuất hiện đầu tiên, loại các bản sau.
    """
    mask = orders.duplicated(subset=["ma_cua_hang", "ma_don"], keep="first")
    reasons = ("Trùng khoá nghiệp vụ: đơn '" + orders["ma_don"].fillna("") + "' của cửa hàng "
               + orders["ma_cua_hang"].fillna("") + " đã xuất hiện ở dòng trước")
    return _result("CL03", "Khoá (cửa hàng, mã đơn) duy nhất", "orders_2024_2026.csv", "LOAI",
                   "ma_cua_hang+ma_don", 0.0, mask, reasons)


def kiem_tra_ngay_trong_khoang(orders: pd.DataFrame, stores: pd.DataFrame,
                               today: date | None = None) -> CheckResult:
    """CL04 — Quy tắc nghiệp vụ: ngày bán phải >= ngày khai trương cửa hàng và <= hôm nay.

    Chỉ áp dụng cho dòng đã có ngày đọc được và cửa hàng hợp lệ (dòng lỗi CL01/CL02
    đã bị loại bởi quy tắc tương ứng, không tính lỗi hai lần).
    """
    today = today or date.today()
    open_map = {
        r.store_code: parse_ngay(_iso_to_dmy(r.ngay_khai_truong))[0]
        for r in stores.itertuples()
    }
    sd = pd.to_datetime(orders["ngay"].map(lambda v: parse_ngay(v)[0]))
    od = pd.to_datetime(orders["ma_cua_hang"].map(open_map))
    before_open = sd.notna() & od.notna() & (sd < od)
    in_future = sd.notna() & (sd > pd.Timestamp(today))
    mask = before_open | in_future
    reasons = pd.Series("", index=orders.index)
    reasons[before_open] = ("Ngày bán " + sd[before_open].dt.strftime("%d/%m/%Y")
                            + " trước ngày khai trương cửa hàng " + orders["ma_cua_hang"][before_open]
                            + " (" + od[before_open].dt.strftime("%d/%m/%Y") + ")")
    reasons[in_future] = "Ngày bán " + sd[in_future].dt.strftime("%d/%m/%Y") + " nằm trong tương lai"
    return _result("CL04", "Ngày bán trong khoảng hoạt động của cửa hàng", "orders_2024_2026.csv",
                   "LOAI", "ngay", 0.0, mask, reasons)


def kiem_tra_tong_tien_don(orders: pd.DataFrame) -> CheckResult:
    """CL05 — Tổng tiền ở đầu đơn: trống hoặc ghi dạng văn bản ('1.234.000đ').

    GHI_NHAN: doanh thu được tính từ dòng hàng (grain fact), không dùng cột này,
    nên lỗi ở đây chỉ được đo và báo cáo, không loại đơn.
    """
    raw = orders["thanh_tien"]
    empty = raw.isna() | (raw.fillna("") == "")
    texty = raw.map(la_dang_van_ban) & ~empty
    unreadable = ~empty & raw.map(lambda v: parse_tien(v) is None)
    mask = empty | texty | unreadable
    reasons = pd.Series("", index=orders.index)
    reasons[empty] = "Tổng tiền đơn để trống"
    reasons[texty] = "Tổng tiền đơn ghi dạng văn bản: '" + raw[texty].fillna("") + "'"
    reasons[unreadable] = "Tổng tiền đơn không phải số: '" + raw[unreadable].fillna("") + "'"
    return _result("CL05", "Tổng tiền đơn đúng kiểu số", "orders_2024_2026.csv", "GHI_NHAN",
                   "thanh_tien", 5.0, mask, reasons)


# ------------------------------------------------------------------ DÒNG HÀNG
def kiem_tra_so_luong_don_gia(items: pd.DataFrame) -> CheckResult:
    """CL06 — Số lượng là số nguyên > 0 và đơn giá là số tiền > 0."""
    qty = items["so_luong"].map(parse_so_nguyen_duong)
    price = items["don_gia"].map(parse_tien)
    bad_qty = qty.isna()
    bad_price = price.isna() | (price.fillna(0) <= 0)
    mask = bad_qty | bad_price
    reasons = pd.Series("", index=items.index)
    reasons[bad_price] = "Đơn giá '" + items["don_gia"].fillna("(trống)")[bad_price] + "' không phải số tiền dương"
    reasons[bad_qty] = "Số lượng '" + items["so_luong"].fillna("(trống)")[bad_qty] + "' không phải số nguyên dương"
    return _result("CL06", "Số lượng & đơn giá dương", "order_items.csv", "LOAI",
                   "so_luong/don_gia", 0.5, mask, reasons)


def kiem_tra_san_pham_ton_tai(items: pd.DataFrame, valid_product_ids: set[str]) -> CheckResult:
    """CL07 — Mã sản phẩm của dòng hàng phải có trong danh mục sản phẩm hợp lệ."""
    mask = ~items["product_id"].isin(valid_product_ids)
    reasons = "Sản phẩm id='" + items["product_id"].fillna("(trống)") + "' không có trong danh mục sản phẩm"
    return _result("CL07", "Sản phẩm tồn tại trong danh mục", "order_items.csv", "LOAI",
                   "product_id", 0.0, mask, reasons)


def kiem_tra_thanh_tien_dong_hang(items: pd.DataFrame) -> CheckResult:
    """CL08 — thanh_tien của dòng hàng phải bằng so_luong × don_gia.

    SUA: so_luong và don_gia là hai giá trị gốc nhập tại quầy; thanh_tien là giá trị
    dẫn xuất nên khi lệch, hệ thống tính lại = so_luong × don_gia và ghi fix_log.
    """
    qty = items["so_luong"].map(parse_so_nguyen_duong)
    price = items["don_gia"].map(parse_tien)
    amount = items["thanh_tien"].map(parse_tien)
    expected = qty * price
    comparable = qty.notna() & price.notna()
    mask = comparable & (amount.isna() | (amount != expected))
    reasons = ("Thành tiền " + items["thanh_tien"].fillna("(trống)") + " ≠ " + items["so_luong"].fillna("")
               + " × " + items["don_gia"].fillna("") + " = " + expected.map(
                   lambda v: "" if pd.isna(v) else f"{int(v)}"))
    return _result("CL08", "Thành tiền dòng = SL × đơn giá", "order_items.csv", "SUA",
                   "thanh_tien", 3.0, mask, reasons)


def kiem_tra_don_cha(items: pd.DataFrame, valid_order_ids: set[str]) -> CheckResult:
    """CL09 — Dòng hàng phải thuộc một đơn hàng hợp lệ (đơn cha không bị loại)."""
    mask = ~items["order_id"].isin(valid_order_ids)
    reasons = ("Đơn hàng cha order_id=" + items["order_id"].fillna("(trống)")
               + " bị loại hoặc không tồn tại nên dòng hàng không được nạp")
    return _result("CL09", "Dòng hàng thuộc đơn hợp lệ", "order_items.csv", "LOAI",
                   "order_id", 2.0, mask, reasons)


# ------------------------------------------------------------------ DANH MỤC
def kiem_tra_san_pham_hop_le(products: pd.DataFrame, cost_ratio: dict[str, float]) -> CheckResult:
    """CL10 — Sản phẩm phải có giá niêm yết dương và nhóm sản phẩm có tỷ lệ giá vốn."""
    price = products["gia_niem_yet"].map(parse_tien)
    bad_price = price.isna() | (price.fillna(0) <= 0)
    no_ratio = ~products["nhom_san_pham"].isin(cost_ratio.keys())
    mask = bad_price | no_ratio
    reasons = pd.Series("", index=products.index)
    reasons[no_ratio] = ("Nhóm sản phẩm '" + products["nhom_san_pham"].fillna("(trống)")[no_ratio]
                         + "' chưa có tỷ lệ giá vốn trong data/reference/ty_le_gia_von.csv")
    reasons[bad_price] = "Giá niêm yết '" + products["gia_niem_yet"].fillna("(trống)")[bad_price] + "' không hợp lệ"
    return _result("CL10", "Sản phẩm đủ giá & nhóm", "products.csv", "LOAI",
                   "gia_niem_yet/nhom_san_pham", 0.0, mask, reasons)


def danh_gia_ti_le_hop_le(rows_loaded: int, rows_extracted: int, threshold: float) -> tuple[float, bool]:
    """Tỉ lệ hợp lệ (%) = dòng nạp / dòng trích xuất × 100; đạt khi >= ngưỡng (biên tính là ĐẠT)."""
    if rows_extracted <= 0:
        return 0.0, False
    rate = round(rows_loaded / rows_extracted * 100, 2)
    return rate, rate >= threshold


def _iso_to_dmy(iso: str | None) -> str | None:
    """'2020-04-30' => '30/04/2020' để dùng chung parse_ngay."""
    if not iso or len(str(iso)) != 10:
        return None
    y, m, d = str(iso).split("-")
    return f"{d}/{m}/{y}"
