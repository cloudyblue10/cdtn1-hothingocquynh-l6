"""PHA TRANSFORM — áp các hàm kiểm chất lượng, tách dòng sạch / dòng reject,
dựng các bảng dimension và fact đúng GRAIN đã chốt ở BT1.

Đầu vào : các DataFrame staging từ pha extract (toàn chuỗi).
Đầu ra  : TransformResult — các DataFrame sẵn sàng nạp + danh sách reject/fix + kết quả kiểm.
Lớp này KHÔNG mở kết nối CSDL (việc đó thuộc src/load).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.quality import checks as Q
from src.transform.rules import (co_hoa_don_vat, date_key, parse_ngay, parse_so_nguyen_duong,
                                 parse_tien, phan_loai_thanh_toan, tinh_chi_so_dong_hang)

# Hợp đồng ở ranh giới transform → load: đúng tên và thứ tự cột của fact
FACT_COLUMNS = [
    "order_code", "line_no", "source_order_id", "sale_date", "date_key", "store_code",
    "product_code", "channel_code", "payment_code", "quantity", "unit_list_price",
    "unit_sale_price", "gross_amount", "discount_amount", "net_revenue", "cogs_amount",
    "gross_profit", "has_vat_invoice",
]

CHANNELS = pd.DataFrame([
    # Bộ dữ liệu chỉ có đơn bán tại 24 cửa hàng => một kênh duy nhất (xem thay-doi-thiet-ke.md)
    {"channel_code": "POS", "channel_name": "Cửa hàng (POS)"},
])
PAYMENTS = pd.DataFrame([
    {"payment_code": "TRA_THANG", "payment_method": "Trả thẳng tại quầy"},
    {"payment_code": "TRA_GOP", "payment_method": "Trả góp 0%"},
])
META = ["_source_file", "_row_number", "line_no"]  # cột kỹ thuật, không thuộc dòng gốc


@dataclass
class TransformResult:
    dim_store: pd.DataFrame
    dim_product: pd.DataFrame
    dim_date: pd.DataFrame
    dim_channel: pd.DataFrame
    dim_payment: pd.DataFrame
    fact: pd.DataFrame
    rejects: pd.DataFrame
    fixes: pd.DataFrame
    checks: list[Q.CheckResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# ------------------------------------------------------------------ tiện ích
def _raw_json(row: pd.Series) -> str:
    data = {k: (None if pd.isna(v) else v) for k, v in row.items() if k not in META}
    return json.dumps(data, ensure_ascii=False, default=str)


def _rows_from_check(df: pd.DataFrame, chk: Q.CheckResult) -> list[dict]:
    """Chuyển các dòng lỗi của một CheckResult thành bản ghi reject/fix."""
    out = []
    raw_col = chk.field_name if chk.field_name in df.columns else None
    for idx in df.index[chk.failed_mask]:
        row = df.loc[idx]
        out.append({
            "source_file": row["_source_file"],
            "row_number": int(row["_row_number"]),
            "rule_code": chk.rule_code,
            "field_name": chk.field_name,
            "raw_value": None if raw_col is None or pd.isna(row[raw_col]) else str(row[raw_col]),
            "reason": chk.reasons[idx],
            "raw_data": _raw_json(row),
        })
    return out


# ------------------------------------------------------------------ dimension
def build_dim_store(stores: pd.DataFrame, regions: pd.DataFrame) -> pd.DataFrame:
    region_map = dict(zip(regions["thanh_pho"], regions["vung_mien"]))
    return pd.DataFrame({
        "store_code": stores["store_code"],
        "store_name": stores["store_name"],
        "region": stores["thanh_pho"].map(region_map).fillna("Chưa phân vùng"),
        "city": stores["thanh_pho"],
        "district": stores["quan_huyen"],
        "open_date": stores["ngay_khai_truong"],
        "is_active": 1,
    }).drop_duplicates("store_code")


def build_dim_product(products: pd.DataFrame, cost_ratio: dict[str, float]) -> pd.DataFrame:
    price = products["gia_niem_yet"].map(parse_tien).astype(float)
    ratio = products["nhom_san_pham"].map(cost_ratio).astype(float)
    return pd.DataFrame({
        "product_code": products["product_code"],
        "source_product_id": products["product_id"].astype(int),
        "product_name": products["product_name"],
        "brand": products["thuong_hieu"],
        "category_name": products["nhom_san_pham"],
        "list_price": price,
        "unit_cost": (price * ratio).round(0),
        "cost_ratio": ratio,
    })


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    uniq = sorted({d for d in dates if d is not None})
    return pd.DataFrame([{
        "date_key": date_key(d), "full_date": d.isoformat(), "day_of_week": d.isoweekday(),
        "day": d.day, "month": d.month, "quarter": (d.month - 1) // 3 + 1, "year": d.year,
    } for d in uniq], columns=["date_key", "full_date", "day_of_week", "day", "month", "quarter", "year"])


# ------------------------------------------------------------------ chính
def transform(frames: dict[str, pd.DataFrame], quality_threshold: float = 95.0,
              today: date | None = None) -> TransformResult:
    orders = frames["orders_2024_2026.csv"].copy()
    items = frames["order_items.csv"].copy()
    products = frames["products.csv"].copy()
    stores = frames["stores.csv"].copy()
    cost_ratio = {
        r.nhom_san_pham: float(r.ty_le_gia_von)
        for r in frames["ty_le_gia_von.csv"].itertuples()
    }

    # line_no tính trên TOÀN BỘ dòng hàng nguồn => ổn định giữa các lần chạy
    items["line_no"] = items.groupby("order_id").cumcount() + 1

    # ---- 1. Danh mục
    dim_store = build_dim_store(stores, frames["vung_mien.csv"])
    chk_prod = Q.kiem_tra_san_pham_hop_le(products, cost_ratio)
    valid_products = products[~chk_prod.failed_mask]
    dim_product = build_dim_product(valid_products, cost_ratio)

    # ---- 2. Đơn hàng
    c01 = Q.kiem_tra_ngay_ban(orders)
    c02 = Q.kiem_tra_ma_cua_hang(orders, stores)
    c03 = Q.kiem_tra_trung_khoa_don(orders)
    c04 = Q.kiem_tra_ngay_trong_khoang(orders, stores, today)
    c05 = Q.kiem_tra_tong_tien_don(orders)
    order_bad = c01.failed_mask | c02.failed_mask | c03.failed_mask | c04.failed_mask
    good_orders = orders[~order_bad].copy()

    # ---- 3. Dòng hàng
    c06 = Q.kiem_tra_so_luong_don_gia(items)
    c07 = Q.kiem_tra_san_pham_ton_tai(items, set(valid_products["product_id"]))
    c09 = Q.kiem_tra_don_cha(items, set(good_orders["order_id"]))
    c08 = Q.kiem_tra_thanh_tien_dong_hang(items)
    item_bad = c06.failed_mask | c07.failed_mask | c09.failed_mask
    good_items = items[~item_bad].copy()

    all_checks = [c01, c02, c03, c04, c05, c06, c07, c08, c09, chk_prod]

    # ---- 4. Fact (grain = 1 dòng sản phẩm trong 1 đơn)
    good_orders["sale_date"] = good_orders["ngay"].map(lambda v: parse_ngay(v)[0])
    fact = _join_fact(good_items, good_orders, dim_product)
    dim_date = build_dim_date(fact["sale_date"])

    # ---- 5. Reject & fix
    rejects: list[dict] = []
    for chk, df in ((c01, orders), (c02, orders), (c03, orders), (c04, orders),
                    (c06, items), (c07, items), (c09, items), (chk_prod, products)):
        rejects.extend(_rows_from_check(df, chk))
    fixes = []
    for idx in items.index[c08.failed_mask & ~item_bad]:   # dòng đã bị loại thì không cần sửa
        row = items.loc[idx]
        q, p = parse_so_nguyen_duong(row["so_luong"]), parse_tien(row["don_gia"])
        fixes.append({"source_file": row["_source_file"], "row_number": int(row["_row_number"]),
                      "rule_code": c08.rule_code, "field_name": c08.field_name,
                      "old_value": row["thanh_tien"], "new_value": str(q * p),
                      "reason": c08.reasons[idx] + " — đã tính lại theo SL × đơn giá"})

    rejects_df = pd.DataFrame(rejects, columns=["source_file", "row_number", "rule_code", "field_name",
                                                "raw_value", "reason", "raw_data"])
    fixes_df = pd.DataFrame(fixes, columns=["source_file", "row_number", "rule_code", "field_name",
                                            "old_value", "new_value", "reason"])

    # ---- 6. Thống kê lần chạy
    rows_extracted = len(orders) + len(items)
    rows_rejected = int(order_bad.sum() + item_bad.sum())
    rows_loaded = len(good_orders) + len(fact)
    valid_rate, valid_ok = Q.danh_gia_ti_le_hop_le(rows_loaded, rows_extracted, quality_threshold)
    stats = {
        "orders_extracted": len(orders), "items_extracted": len(items),
        "orders_loaded": len(good_orders), "fact_rows": len(fact),
        "rows_extracted": rows_extracted, "rows_loaded": rows_loaded,
        "rows_rejected": rows_rejected, "rows_fixed": len(fixes_df),
        "valid_rate": valid_rate, "valid_rate_passed": valid_ok,
        "quality_threshold": quality_threshold,
    }
    return TransformResult(dim_store, dim_product, dim_date, CHANNELS.copy(), PAYMENTS.copy(),
                           fact, rejects_df, fixes_df, all_checks, stats)


def _join_fact(good_items: pd.DataFrame, good_orders: pd.DataFrame,
               dim_product: pd.DataFrame) -> pd.DataFrame:
    """Ghép dòng hàng + đơn hàng + sản phẩm và tính các chỉ số tài chính."""
    gi = good_items.copy()
    gi["source_product_id"] = gi["product_id"].astype(int)
    df = gi.merge(good_orders[["order_id", "ma_don", "ma_cua_hang", "sale_date", "ghi_chu"]],
                  on="order_id", how="inner", validate="many_to_one")
    df = df.merge(dim_product[["source_product_id", "product_code", "list_price", "unit_cost"]],
                  on="source_product_id", how="inner", validate="many_to_one")

    qty = df["so_luong"].map(parse_so_nguyen_duong)
    sale = df["don_gia"].map(parse_tien).astype(float)
    lst = df["list_price"].astype(float)
    # Một nơi duy nhất chứa công thức: rules.tinh_chi_so_dong_hang (đã có unit test)
    metrics = pd.DataFrame(
        [tinh_chi_so_dong_hang(q, lp, sp, uc)
         for q, lp, sp, uc in zip(qty, lst, sale, df["unit_cost"].astype(float))],
        columns=["gross_amount", "discount_amount", "net_revenue", "cogs_amount", "gross_profit"],
        index=df.index,
    )

    return pd.DataFrame({
        "order_code": df["ma_don"],
        "line_no": df["line_no"].astype(int),
        "source_order_id": df["order_id"].astype(int),
        "sale_date": df["sale_date"],
        "date_key": df["sale_date"].map(date_key),
        "store_code": df["ma_cua_hang"],
        "product_code": df["product_code"],
        "channel_code": "POS",
        "payment_code": df["ghi_chu"].map(phan_loai_thanh_toan),
        "quantity": qty.astype(int),
        "unit_list_price": lst,
        "unit_sale_price": sale,
        **{c: metrics[c] for c in metrics.columns},
        "has_vat_invoice": df["ghi_chu"].map(co_hoa_don_vat).astype(int),
    }, columns=FACT_COLUMNS)
