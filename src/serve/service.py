"""LỚP SERVICE — logic trình bày & nghiệp vụ của dashboard.

* KHÔNG import Flask, KHÔNG biết request/response hay mã HTTP (kiểm tra ranh giới lớp C2).
* KHÔNG viết SQL — mọi truy vấn đi qua WarehouseRepository.
* Nhận tham số dạng dict chuỗi (từ bất kỳ nguồn nào), kiểm tra hợp lệ, trả dict thuần.

Mỗi con số trả về đều kèm một MỐC SO SÁNH: kỳ trước cùng độ dài, trung bình, hoặc ngưỡng.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

from src.serve.errors import ValidationError
from src.serve.repository import Filters, WarehouseRepository
from src.transform.rules import ty_suat_loi_nhuan_gop

STATUS_OK = "ok"
STATUS_EMPTY_WAREHOUSE = "empty_warehouse"   # kho chưa có dữ liệu (chưa chạy pipeline / nguồn rỗng)
STATUS_EMPTY_FILTER = "empty_filter"         # kho có dữ liệu nhưng bộ lọc không ra dòng nào


def _key_to_date(k: int) -> date:
    return date(k // 10000, k // 100 % 100, k % 100)


def _date_to_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def pct_change(current: float, previous: float) -> float | None:
    """% thay đổi so với kỳ trước. Kỳ trước = 0 => None (không chia cho 0)."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def share_pct(part: float, total: float) -> float:
    return round(part / total * 100, 2) if total else 0.0


def detect_alerts(daily: list[dict], threshold: float, window: int = 7) -> list[dict]:
    """FR-11: ngày có doanh thu lệch > threshold% so với trung bình `window` ngày liền trước."""
    alerts = []
    for i in range(window, len(daily)):
        base = sum(d["net_revenue"] for d in daily[i - window:i]) / window
        if base <= 0:
            continue
        change = (daily[i]["net_revenue"] - base) / base * 100
        if abs(change) > threshold:
            alerts.append({"day": daily[i]["day"], "net_revenue": daily[i]["net_revenue"],
                           "baseline": round(base, 0), "change_pct": round(change, 1),
                           "direction": "tăng" if change > 0 else "giảm"})
    return alerts


class DashboardService:
    def __init__(self, repo: WarehouseRepository, alert_threshold: float = 30.0,
                 quality_threshold: float = 95.0):
        self.repo = repo
        self.alert_threshold = alert_threshold
        self.quality_threshold = quality_threshold

    # ------------------------------------------------------------ bộ lọc
    def parse_filters(self, params: dict) -> Filters:
        """Đọc & kiểm tra bộ lọc. Không truyền ngày => mặc định THÁNG GẦN NHẤT CÓ DỮ LIỆU."""
        rng = self.repo.date_range()
        max_key = rng["max_key"]
        if max_key:
            last = _key_to_date(max_key)
            default_from, default_to = last.replace(day=1), last
        else:
            default_to = date.today()
            default_from = default_to.replace(day=1)

        d_from = self._parse_date(params.get("from"), "from", "Từ ngày") or default_from
        d_to = self._parse_date(params.get("to"), "to", "Đến ngày") or default_to
        if d_from > d_to:
            raise ValidationError(
                f"Từ ngày ({d_from:%d/%m/%Y}) đang sau Đến ngày ({d_to:%d/%m/%Y}).",
                "Chọn lại khoảng thời gian sao cho Từ ngày trước hoặc bằng Đến ngày.", field="from")

        store = (params.get("store") or "").strip() or None
        if store and store not in {s["store_code"] for s in self.repo.stores()}:
            raise ValidationError(f"Không có cửa hàng mã '{store}'.",
                                  "Chọn cửa hàng trong danh sách hoặc chọn 'Tất cả'.", field="store")
        category = (params.get("category") or "").strip() or None
        if category and category not in self.repo.categories():
            raise ValidationError(f"Không có danh mục '{category}'.",
                                  "Chọn danh mục trong danh sách hoặc chọn 'Tất cả'.", field="category")
        return Filters(_date_to_key(d_from), _date_to_key(d_to), store, category)

    @staticmethod
    def _parse_date(value: str | None, field: str, label: str) -> date | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(f"{label} '{value}' không phải ngày hợp lệ.",
                                  "Nhập ngày theo dạng yyyy-mm-dd, ví dụ 2026-08-01.", field=field)

    @staticmethod
    def previous_period(f: Filters) -> Filters:
        """Kỳ trước = khoảng cùng số ngày, liền ngay trước khoảng đang xem."""
        d_from, d_to = _key_to_date(f.date_from), _key_to_date(f.date_to)
        length = (d_to - d_from).days + 1
        p_to = d_from - timedelta(days=1)
        p_from = p_to - timedelta(days=length - 1)
        return Filters(_date_to_key(p_from), _date_to_key(p_to), f.store_code, f.category)

    def _describe(self, f: Filters) -> dict:
        d_from, d_to = _key_to_date(f.date_from), _key_to_date(f.date_to)
        parts = [f"{d_from:%d/%m/%Y} – {d_to:%d/%m/%Y}"]
        if f.store_code:
            parts.append(f"cửa hàng {f.store_code}")
        if f.category:
            parts.append(f"danh mục {f.category}")
        return {"from": d_from.isoformat(), "to": d_to.isoformat(), "store": f.store_code,
                "category": f.category, "label": ", ".join(parts)}

    def _status(self, has_rows: bool) -> str:
        if has_rows:
            return STATUS_OK
        return STATUS_EMPTY_WAREHOUSE if self.repo.fact_count() == 0 else STATUS_EMPTY_FILTER

    def _source(self) -> dict:
        runs = self.repo.runs(1)
        return {"updated_at": runs[0]["finished_at"] if runs else None,
                "run_id": runs[0]["run_id"] if runs else None}

    # ------------------------------------------------------------ màn hình
    def meta(self) -> dict:
        rng = self.repo.date_range()
        f = self.parse_filters({})
        return {
            "stores": self.repo.stores(), "categories": self.repo.categories(),
            "min_date": _key_to_date(rng["min_key"]).isoformat() if rng["min_key"] else None,
            "max_date": _key_to_date(rng["max_key"]).isoformat() if rng["max_key"] else None,
            "default_filter": self._describe(f), "has_data": self.repo.fact_count() > 0,
            "source": self._source(),
        }

    def overview(self, params: dict) -> dict:
        f = self.parse_filters(params)
        cur = self.repo.kpis(f)
        prev_f = self.previous_period(f)
        prev = self.repo.kpis(prev_f)
        status = self._status(cur["line_count"] > 0)

        def pack(k: dict) -> dict:
            aov = round(k["net_revenue"] / k["orders"], 0) if k["orders"] else 0
            return {**k, "aov": aov, "margin_pct": ty_suat_loi_nhuan_gop(k["gross_profit"], k["net_revenue"])}

        c, p = pack(cur), pack(prev)
        kpis = {
            m: {"value": c[m], "previous": p[m], "delta_pct": pct_change(c[m] or 0, p[m] or 0)}
            for m in ("net_revenue", "orders", "aov", "gross_profit", "quantity", "discount_amount")
        }
        kpis["margin_pct"] = {"value": c["margin_pct"], "previous": p["margin_pct"],
                              "delta_pt": (round(c["margin_pct"] - p["margin_pct"], 2)
                                           if c["margin_pct"] is not None and p["margin_pct"] is not None
                                           else None)}
        daily = self.repo.daily_series(f) if status == STATUS_OK else []
        avg = round(sum(d["net_revenue"] for d in daily) / len(daily), 0) if daily else 0
        # Cảnh báo cần 7 ngày trước khoảng xem làm nền => lấy thêm 7 ngày phía trước
        ext = Filters(_date_to_key(_key_to_date(f.date_from) - timedelta(days=7)), f.date_to,
                      f.store_code, f.category)
        ext_daily = self.repo.daily_series(ext) if status == STATUS_OK else []
        alerts = [a for a in detect_alerts(ext_daily, self.alert_threshold)
                  if a["day"] >= _key_to_date(f.date_from).isoformat()]
        return {
            "status": status, "filter": self._describe(f), "previous_filter": self._describe(prev_f),
            "kpis": kpis, "daily": daily, "daily_avg_revenue": avg,
            "alerts": {"threshold_pct": self.alert_threshold, "count": len(alerts), "items": alerts[-8:]},
            "source": {**self._source(), "tables": "fact_order_item · agg_daily_store · dim_date · dim_store"},
        }

    def products(self, params: dict) -> dict:
        f = self.parse_filters(params)
        sort = params.get("sort") if params.get("sort") in ("revenue", "quantity") else "revenue"
        search = (params.get("q") or "").strip()[:60] or None
        rows = self.repo.by_product(f, search, sort)
        total = self.repo.kpis(f)["net_revenue"]
        for i, r in enumerate(rows):
            r["share_pct"] = share_pct(r["net_revenue"], total)
            r["margin_pct"] = ty_suat_loi_nhuan_gop(r["gross_profit"], r["net_revenue"])
            r["is_top10"] = i < 10
        cats = self.repo.by_category(f)
        for c in cats:
            c["share_pct"] = share_pct(c["net_revenue"], total)
            c["margin_pct"] = ty_suat_loi_nhuan_gop(c["gross_profit"], c["net_revenue"])
        overall_margin = ty_suat_loi_nhuan_gop(sum(c["gross_profit"] for c in cats), total)
        return {"status": self._status(bool(rows)), "filter": self._describe(f), "sort": sort,
                "search": search, "total_revenue": total, "overall_margin_pct": overall_margin,
                "rows": rows, "categories": cats,
                "source": {**self._source(), "tables": "fact_order_item · dim_product"}}

    def stores(self, params: dict) -> dict:
        f = self.parse_filters({**params, "store": None})   # màn hình này so sánh MỌI cửa hàng
        rows = self.repo.by_store(f)
        total = sum(r["net_revenue"] for r in rows)
        avg = round(total / len(rows), 0) if rows else 0
        prev = {r["store_code"]: r["net_revenue"] for r in self.repo.by_store(self.previous_period(f))}
        for r in rows:
            r["share_pct"] = share_pct(r["net_revenue"], total)
            r["vs_avg_pct"] = pct_change(r["net_revenue"], avg)
            r["delta_pct"] = pct_change(r["net_revenue"], prev.get(r["store_code"], 0))
        return {"status": self._status(bool(rows)), "filter": self._describe(f), "rows": rows,
                "total_revenue": total, "avg_revenue": avg,
                "source": {**self._source(), "tables": "fact_order_item · dim_store"}}

    def payments(self, params: dict) -> dict:
        f = self.parse_filters(params)
        rows = self.repo.by_payment(f)
        total = sum(r["net_revenue"] for r in rows)
        prev_rows = self.repo.by_payment(self.previous_period(f))
        prev_total = sum(r["net_revenue"] for r in prev_rows)
        prev_share = {r["payment_code"]: share_pct(r["net_revenue"], prev_total) for r in prev_rows}
        for r in rows:
            r["share_pct"] = share_pct(r["net_revenue"], total)
            r["prev_share_pct"] = prev_share.get(r["payment_code"])
            r["aov"] = round(r["net_revenue"] / r["orders"], 0) if r["orders"] else 0
        monthly: dict[str, dict] = {}
        for m in self.repo.payment_monthly(f):
            monthly.setdefault(m["month"], {"month": m["month"], "TRA_GOP": 0.0, "TRA_THANG": 0.0})
            monthly[m["month"]][m["payment_code"]] = m["net_revenue"]
        trend = [{"month": v["month"],
                  "installment_share_pct": share_pct(v["TRA_GOP"], v["TRA_GOP"] + v["TRA_THANG"])}
                 for v in monthly.values()]
        avg_share = round(sum(t["installment_share_pct"] for t in trend) / len(trend), 2) if trend else 0
        return {"status": self._status(bool(rows)), "filter": self._describe(f), "rows": rows,
                "total_revenue": total, "installment_trend": trend, "installment_avg_share_pct": avg_share,
                "channel_note": "Bộ dữ liệu chỉ ghi nhận đơn bán tại 24 cửa hàng (POS); chưa có đơn "
                                "Website/App/Shopee/TikTok nên biểu đồ theo kênh chỉ có một kênh.",
                "source": {**self._source(), "tables": "fact_order_item · dim_payment · dim_channel"}}

    def quality(self, params: dict) -> dict:
        runs = self.repo.runs(10)
        ok_runs = [r for r in runs if r["status"] == "SUCCESS"]
        latest_ok = ok_runs[0] if ok_runs else None
        prev_ok = ok_runs[1] if len(ok_runs) > 1 else None
        rule = (params.get("rule") or "").strip().upper() or None
        checks = self.repo.quality_results(latest_ok["run_id"]) if latest_ok else []
        return {
            "status": STATUS_OK if latest_ok else STATUS_EMPTY_WAREHOUSE,
            "threshold_pct": self.quality_threshold,
            "latest_run": runs[0] if runs else None, "latest_success": latest_ok,
            "previous_success": prev_ok, "runs": runs, "checks": checks,
            "reject_counts": self.repo.reject_counts(), "fix_count": self.repo.fix_count(),
            "rejects": self.repo.rejects(rule), "rule_filter": rule,
            "source": {"tables": "etl_run_log · quality_result · reject_records · fix_log"},
        }

    def export_csv(self, params: dict) -> tuple[str, str]:
        """FR-07: xuất 6 trường quy định. Trả về (tên tệp, nội dung CSV có BOM cho Excel)."""
        f = self.parse_filters(params)
        rows = self.repo.export_rows(f)
        buf = io.StringIO()
        cols = ["ngay", "ma_cua_hang", "ma_don", "ma_san_pham", "so_luong", "doanh_thu_thuan"]
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
        name = f"doanh_thu_{f.date_from}_{f.date_to}{'_' + f.store_code if f.store_code else ''}.csv"
        return name, "﻿" + buf.getvalue()
