"""Kiểm thử lớp SERVICE (dùng repository GIẢ) và lớp ROUTES/API (kho tạm do pipeline tạo)."""
from __future__ import annotations

import pytest

from src.serve.app import create_app
from src.serve.errors import ValidationError
from src.serve.repository import Filters, WarehouseRepository
from src.serve.service import DashboardService, detect_alerts, pct_change


class FakeRepo:
    """Repository giả: service được test mà không cần CSDL thật (cô lập lớp)."""

    def __init__(self, line_count=10, fact_count=10):
        self.line_count, self._fact = line_count, fact_count

    def date_range(self): return {"min_key": 20240701, "max_key": 20260831}
    def stores(self): return [{"store_code": "MM001", "store_name": "Q1", "city": "HCM", "region": "ĐNB"}]
    def categories(self): return ["Phụ kiện"]
    def fact_count(self): return self._fact
    def runs(self, n=1): return [{"run_id": "RUN-1", "finished_at": "2026-10-01T10:00:00", "status": "SUCCESS"}]
    def daily_series(self, f): return []

    def kpis(self, f):
        return {"net_revenue": 0, "orders": 0, "quantity": 0, "gross_amount": 0, "discount_amount": 0,
                "cogs_amount": 0, "gross_profit": 0, "line_count": self.line_count}


# ============================================================ LOẠI 1 — LUỒNG ĐÚNG
@pytest.mark.luong_dung
def test_mac_dinh_la_thang_gan_nhat_co_du_lieu():
    f = DashboardService(FakeRepo()).parse_filters({})
    assert (f.date_from, f.date_to) == (20260801, 20260831)


@pytest.mark.luong_dung
def test_ky_truoc_cung_do_dai_lien_ngay_truoc():
    prev = DashboardService.previous_period(Filters(20260801, 20260831))
    assert (prev.date_from, prev.date_to) == (20260701, 20260731)


@pytest.mark.luong_dung
def test_api_tong_quan_tra_dung_hop_dong(run, workspace):
    """Test hợp đồng ở ranh giới API ↔ giao diện: đủ khoá, số liệu khớp kho."""
    run()
    svc = DashboardService(WarehouseRepository(workspace["dw_path"]))
    client = create_app(svc).test_client()
    res = client.get("/api/overview?from=2025-09-01&to=2026-12-31")
    assert res.status_code == 200
    body = res.get_json()
    assert {"status", "filter", "previous_filter", "kpis", "daily", "daily_avg_revenue", "alerts", "source"} <= set(body)
    assert body["status"] == "ok"
    assert body["kpis"]["net_revenue"]["value"] == 34_600_000      # đơn 2, 3, 4 (đơn 1 ngày 17/08/2025 nằm ngoài)
    assert body["kpis"]["orders"]["value"] == 3


@pytest.mark.luong_dung
def test_xuat_csv_dung_6_truong_quy_dinh(run, workspace):
    run()
    client = create_app(DashboardService(WarehouseRepository(workspace["dw_path"]))).test_client()
    res = client.get("/api/export.csv?from=2024-07-01&to=2026-08-31")
    header = res.get_data(as_text=True).lstrip("﻿").splitlines()[0]
    assert header == "ngay,ma_cua_hang,ma_don,ma_san_pham,so_luong,doanh_thu_thuan"
    assert len(res.get_data(as_text=True).strip().splitlines()) == 1 + 5


# ============================================================ LOẠI 2 — GIÁ TRỊ BIÊN
@pytest.mark.gia_tri_bien
def test_canh_bao_chi_khi_lech_vuot_qua_30_phan_tram():
    base = [{"day": f"2026-08-0{i}", "net_revenue": 100.0} for i in range(1, 8)]
    assert detect_alerts(base + [{"day": "2026-08-08", "net_revenue": 130.0}], 30) == []   # đúng 30% => không
    hit = detect_alerts(base + [{"day": "2026-08-08", "net_revenue": 130.1}], 30)
    assert len(hit) == 1 and hit[0]["direction"] == "tăng"


@pytest.mark.gia_tri_bien
def test_tu_ngay_bang_den_ngay_la_hop_le_va_ky_truoc_khi_bang_0():
    f = DashboardService(FakeRepo()).parse_filters({"from": "2026-08-31", "to": "2026-08-31"})
    assert f.date_from == f.date_to == 20260831
    assert pct_change(100, 0) is None


@pytest.mark.gia_tri_bien
def test_bo_loc_khong_ra_dong_nao_khac_kho_rong():
    """Phân biệt 2 kiểu RỖNG: kho có dữ liệu nhưng lọc không khớp vs kho chưa có dữ liệu."""
    assert DashboardService(FakeRepo(line_count=0, fact_count=10)).overview({})["status"] == "empty_filter"
    assert DashboardService(FakeRepo(line_count=0, fact_count=0)).overview({})["status"] == "empty_warehouse"


# ============================================================ LOẠI 3 — DỮ LIỆU SAI
@pytest.mark.du_lieu_sai
def test_tu_ngay_sau_den_ngay_bi_tu_choi_ro_rang():
    with pytest.raises(ValidationError) as e:
        DashboardService(FakeRepo()).parse_filters({"from": "2026-08-31", "to": "2026-08-01"})
    assert e.value.field == "from" and "sau Đến ngày" in e.value.message


@pytest.mark.du_lieu_sai
def test_api_ngay_sai_va_cua_hang_la_tra_400_kem_ten_truong(run, workspace):
    run()
    client = create_app(DashboardService(WarehouseRepository(workspace["dw_path"]))).test_client()
    r1 = client.get("/api/overview?from=31-08-2026")
    assert r1.status_code == 400 and r1.get_json()["error"]["field"] == "from"
    r2 = client.get("/api/products?store=MM999")
    assert r2.status_code == 400 and "MM999" in r2.get_json()["error"]["message"]


@pytest.mark.du_lieu_sai
def test_mat_ket_noi_kho_tra_503_thong_bao_than_thien(tmp_path):
    """Tắt thành phần phía sau (kho không tồn tại) => 503 + thông điệp cho người dùng, không lộ lỗi thô."""
    client = create_app(DashboardService(WarehouseRepository(tmp_path / "khong_co.sqlite"))).test_client()
    res = client.get("/api/overview")
    body = res.get_json()
    assert res.status_code == 503
    assert body["error"]["code"] == "DW_UNAVAILABLE"
    assert body["error"]["message"].startswith("Không thể kết nối tới Kho dữ liệu")
    assert "Traceback" not in res.get_data(as_text=True) and "sqlite3" not in res.get_data(as_text=True)
