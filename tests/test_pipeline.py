"""Kiểm thử TÍCH HỢP pipeline E → T → L trên bộ nguồn mini tự dựng (tests/conftest.py)."""
from __future__ import annotations

import json

import pytest

from src.extract.extract import SourceSchemaError
from tests.conftest import ITEMS, ORDERS, query, write_csv


# ============================================================ LOẠI 1 — LUỒNG ĐÚNG
@pytest.mark.luong_dung
def test_nguon_dung_dinh_dang_thi_nap_du_so_dong(run, workspace):
    """Tệp nguồn đúng định dạng (đủ 3 kiểu ngày) => nạp đủ 4 đơn / 5 dòng hàng, không reject."""
    r = run()
    dw = workspace["dw_path"]
    assert r["status"] == "SUCCESS"
    assert query(dw, "SELECT COUNT(*) FROM fact_order_item")[0][0] == len(ITEMS) - 1
    assert query(dw, "SELECT COUNT(DISTINCT store_key||order_code) FROM fact_order_item")[0][0] == len(ORDERS) - 1
    assert query(dw, "SELECT COUNT(*) FROM reject_records")[0][0] == 0
    assert r["valid_rate"] == 100.0
    # 3 định dạng ngày đều được đọc đúng
    days = {d for (d,) in query(dw, "SELECT full_date FROM dim_date")}
    assert days == {"2025-08-17", "2026-06-02", "2025-12-19", "2026-08-01"}


@pytest.mark.luong_dung
def test_chi_so_tai_chinh_dung_cong_thuc_bt1(run, workspace):
    """Đơn 3: giá niêm yết 2.000.000, bán 1.800.000, giá vốn 80% => giảm 200k, LN gộp 200k."""
    run()
    row = query(workspace["dw_path"],
                """SELECT gross_amount, discount_amount, net_revenue, cogs_amount, gross_profit
                   FROM fact_order_item WHERE order_code='MM001-0002'""")[0]
    assert row == (2_000_000, 200_000, 1_800_000, 1_600_000, 200_000)


@pytest.mark.luong_dung
def test_chay_lai_lan_hai_khong_nhan_doi_du_lieu(run, workspace):
    """C5: chạy hai lần cùng đầu vào => số dòng mọi bảng đích KHÔNG đổi; nhật ký có 2 lần chạy."""
    dw = workspace["dw_path"]
    tables = ["fact_order_item", "dim_store", "dim_product", "dim_date", "agg_daily_store",
              "reject_records", "fix_log"]
    run()
    first = {t: query(dw, f"SELECT COUNT(*) FROM {t}")[0][0] for t in tables}
    run()
    second = {t: query(dw, f"SELECT COUNT(*) FROM {t}")[0][0] for t in tables}
    assert first == second
    assert query(dw, "SELECT COUNT(*) FROM etl_run_log WHERE status='SUCCESS'")[0][0] == 2
    assert query(dw, "SELECT SUM(net_revenue) FROM fact_order_item")[0][0] == 36_600_000


# ============================================================ LOẠI 2 — GIÁ TRỊ BIÊN
@pytest.mark.gia_tri_bien
def test_ngay_ban_dung_ngay_khai_truong_duoc_nhan_truoc_mot_ngay_bi_loai(run, workspace):
    """CL04: MM002 khai trương 10/07/2024. Bán đúng 10/07/2024 => NHẬN; 09/07/2024 => LOẠI."""
    orders = ORDERS + [
        [10, "HD00010", "MM002", "10/07/2024", "Biên", "", "2000000", "", ""],
        [11, "HD00011", "MM002", "09/07/2024", "Biên", "", "2000000", "", ""],
    ]
    items = ITEMS + [[10, 1, 1, 2000000, 2000000], [11, 1, 1, 2000000, 2000000]]
    write_csv(workspace["data_dir"] / "orders_2024_2026.csv", orders)
    write_csv(workspace["data_dir"] / "order_items.csv", items)
    run()
    dw = workspace["dw_path"]
    loaded = {c for (c,) in query(dw, "SELECT order_code FROM fact_order_item")}
    assert "HD00010" in loaded
    assert "HD00011" not in loaded
    reason = query(dw, "SELECT reason FROM reject_records WHERE rule_code='CL04'")[0][0]
    assert "trước ngày khai trương" in reason and "10/07/2024" in reason


@pytest.mark.gia_tri_bien
def test_ma_don_trung_khac_cua_hang_hop_le_trung_ca_cap_bi_loai(run, workspace):
    """CL03: 'HD00001' ở MM001 và MM002 là 2 đơn khác nhau (đã nạp). Trùng cả cặp => loại bản sau."""
    orders = ORDERS + [[12, "HD00001", "MM001", "20/08/2025", "Lặp", "", "2000000", "", ""]]
    write_csv(workspace["data_dir"] / "orders_2024_2026.csv", orders)
    write_csv(workspace["data_dir"] / "order_items.csv", ITEMS + [[12, 1, 1, 2000000, 2000000]])
    run()
    dw = workspace["dw_path"]
    assert query(dw, "SELECT COUNT(DISTINCT store_key) FROM fact_order_item WHERE order_code='HD00001'")[0][0] == 2
    rej = query(dw, "SELECT row_number FROM reject_records WHERE rule_code='CL03'")
    assert rej == [(6,)]   # dòng 6 trong tệp (tiêu đề là dòng 1)


# ============================================================ LOẠI 3 — DỮ LIỆU SAI
@pytest.mark.du_lieu_sai
def test_ngay_khong_doc_duoc_vao_bang_reject_kem_ly_do(run, workspace):
    """Ngày '31/02/2025', 'hôm qua' và ô trống => vào reject kèm lý do đọc được; pipeline KHÔNG sập."""
    orders = ORDERS + [
        [20, "HD00020", "MM001", "31/02/2025", "X", "", "1", "", ""],
        [21, "HD00021", "MM001", "hôm qua", "Y", "", "1", "", ""],
        [22, "HD00022", "MM001", "", "Z", "", "1", "", ""],
    ]
    items = ITEMS + [[20, 1, 1, 2000000, 2000000], [21, 1, 1, 2000000, 2000000], [22, 1, 1, 2000000, 2000000]]
    write_csv(workspace["data_dir"] / "orders_2024_2026.csv", orders)
    write_csv(workspace["data_dir"] / "order_items.csv", items)
    r = run()
    assert r["status"] == "SUCCESS" and r["rows_rejected"] == 6   # 3 đơn + 3 dòng hàng con
    reasons = dict(query(workspace["dw_path"],
                         "SELECT raw_value, reason FROM reject_records WHERE rule_code='CL01'"))
    assert reasons["31/02/2025"] == "Ngày bán '31/02/2025' không tồn tại trên lịch"
    assert "không thuộc định dạng nào" in reasons["hôm qua"]
    assert reasons[None] == "Ngày bán để trống"          # ô trống lưu raw_value = NULL
    raw = json.loads(query(workspace["dw_path"],
                           "SELECT raw_data FROM reject_records WHERE rule_code='CL01' LIMIT 1")[0][0])
    assert raw["ma_don"] == "HD00020"   # lưu nguyên dòng gốc để truy vết


@pytest.mark.du_lieu_sai
def test_thanh_tien_dong_hang_sai_duoc_sua_va_ghi_fix_log(run, workspace):
    """CL08: thanh_tien 1.100.000 ≠ 2 × 500.000 => giữ dòng, tính lại 1.000.000, ghi fix_log."""
    items = [r[:] for r in ITEMS]
    items[3][4] = 1100000                       # dòng (2, 3, 2, 500000) — ghi sai thành tiền
    write_csv(workspace["data_dir"] / "order_items.csv", items)
    r = run()
    dw = workspace["dw_path"]
    assert r["rows_fixed"] == 1
    assert query(dw, "SELECT old_value, new_value FROM fix_log")[0] == ("1100000", "1000000")
    assert query(dw, "SELECT net_revenue FROM fact_order_item WHERE product_key="
                     "(SELECT product_key FROM dim_product WHERE product_code='XM0003')")[0][0] == 1_000_000


@pytest.mark.du_lieu_sai
def test_tep_thieu_cot_bat_buoc_bao_loi_ro_rang_va_giu_nguyen_kho(run, workspace):
    """Thiếu cột 'ngay' => SourceSchemaError nêu TÊN cột; nhật ký ghi FAILED; dữ liệu cũ còn nguyên."""
    run()
    dw = workspace["dw_path"]
    before = query(dw, "SELECT COUNT(*) FROM fact_order_item")[0][0]
    bad = [[c for i, c in enumerate(r) if i != 3] for r in ORDERS]     # bỏ cột thứ 4 = 'ngay'
    write_csv(workspace["data_dir"] / "orders_2024_2026.csv", bad)
    with pytest.raises(SourceSchemaError, match="thiếu cột bắt buộc: ngay"):
        run()
    assert query(dw, "SELECT COUNT(*) FROM fact_order_item")[0][0] == before
    status, msg = query(dw, "SELECT status, error_message FROM etl_run_log ORDER BY rowid DESC LIMIT 1")[0]
    assert status == "FAILED" and "ngay" in msg
