#!/usr/bin/env python3
"""Pipeline ETL L6 – Kho dữ liệu bán hàng (BT1 → BT2)."""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.extract import extract_orders, extract_order_items, extract_stores, extract_products
from src.transform import (
    clean_orders, clean_order_items, clean_stores, clean_products,
    build_dim_store, build_dim_product, build_dim_date, build_dim_channel, build_dim_payment,
    build_fact_order_item,
)
from src.quality import run_all_checks
from src.load import get_conn, load_all


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    use_sample = not args.full and os.getenv("USE_SAMPLE", "true").lower() in ("1", "true", "yes")
    reject_dir = Path(os.getenv("REJECT_DIR", "data/reject"))
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    reject_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MEKONG MOBILE – KHO DỮ LIỆU BÁN HÀNG (L6)")
    print(f"Thời điểm : {datetime.now().isoformat(timespec='seconds')}")
    print(f"Dữ liệu   : {'SAMPLE' if use_sample else 'FULL'}")
    print("=" * 60)

    print("\n[1/4] EXTRACT")
    orders_raw = extract_orders(use_sample=use_sample)
    items_raw = extract_order_items(use_sample=use_sample)
    stores_raw = extract_stores(use_sample=use_sample)
    products_raw = extract_products(use_sample=use_sample)
    print(f"  orders={len(orders_raw):,}  items={len(items_raw):,}  stores={len(stores_raw):,}  products={len(products_raw):,}")

    print("\n[2/4] QUALITY")
    quality_results = run_all_checks(orders_raw, items_raw)
    for r in quality_results:
        st = "OK" if r["error_rows"] == 0 else "WARN"
        print(f"  [{st}] {r['name']}: {r['error_rows']}/{r['total_rows']} ({r['error_rate']}%)")

    print("\n[3/4] TRANSFORM")
    orders_c, orders_rj = clean_orders(orders_raw)
    items_c, items_rj = clean_order_items(items_raw)
    stores_c, stores_rj = clean_stores(stores_raw)
    products_c, products_rj = clean_products(products_raw)
    print(f"  orders clean/reject : {len(orders_c):,} / {len(orders_rj):,}")
    print(f"  items  clean/reject : {len(items_c):,} / {len(items_rj):,}")

    rejects = {"orders": orders_rj, "order_items": items_rj, "stores": stores_rj, "products": products_rj}
    for name, rdf in rejects.items():
        if len(rdf):
            rdf.to_csv(reject_dir / f"{name}_reject.csv", index=False)

    dim_store = build_dim_store(stores_c)
    dim_product = build_dim_product(products_c)
    dim_date = build_dim_date(orders_c)
    dim_channel = build_dim_channel(orders_c)
    dim_payment = build_dim_payment(orders_c)
    fact = build_fact_order_item(orders_c, items_c, dim_store, dim_product, dim_date, dim_channel, dim_payment)
    print(f"  dim_store={len(dim_store)} dim_product={len(dim_product)} dim_date={len(dim_date)}")
    print(f"  dim_channel={len(dim_channel)} dim_payment={len(dim_payment)}")
    print(f"  fact_order_item={len(fact):,}")

    print("\n[4/4] LOAD")
    conn = get_conn()
    counts = load_all(conn, dim_store, dim_product, dim_date, dim_channel, dim_payment, fact, rejects, quality_results)
    conn.close()
    for k, v in counts.items():
        print(f"  {k}: {v:,}")

    # export chart data
    import pandas as pd
    m = fact.merge(dim_date, on="date_key").merge(dim_store, on="store_key").merge(dim_product, on="product_key")
    m = m.merge(dim_channel, on="channel_key").merge(dim_payment, on="payment_key")
    by_month = m.groupby(["year", "month"], as_index=False).agg(net_revenue=("net_revenue", "sum"), so_don=("order_id", "nunique"))
    by_store = m.groupby(["store_name", "city"], as_index=False)["net_revenue"].sum().sort_values("net_revenue", ascending=False).head(10)
    by_product = m.groupby(["product_code", "product_name", "category_name"], as_index=False).agg(
        quantity=("quantity", "sum"), net_revenue=("net_revenue", "sum"), cogs_amount=("cogs_amount", "sum"), gross_profit=("gross_profit", "sum")
    ).sort_values("net_revenue", ascending=False).head(10)
    by_channel = m.groupby("channel_name", as_index=False)["net_revenue"].sum()
    by_payment = m.groupby("payment_method", as_index=False).agg(so_don=("order_id", "nunique"), net_revenue=("net_revenue", "sum"))

    by_month.to_csv(output_dir / "doanh_thu_theo_thang.csv", index=False)
    by_store.to_csv(output_dir / "top_cua_hang.csv", index=False)
    by_product.to_csv(output_dir / "top_san_pham.csv", index=False)
    by_channel.to_csv(output_dir / "theo_kenh.csv", index=False)
    by_payment.to_csv(output_dir / "theo_thanh_toan.csv", index=False)

    tong_nr = float(fact["net_revenue"].sum())
    tong_gp = float(fact["gross_profit"].sum())
    so_don = int(fact["order_id"].nunique())
    aov = tong_nr / so_don if so_don else 0
    kpi = {
        "tong_doanh_thu_thuan": tong_nr,
        "tong_loi_nhuan_gop": tong_gp,
        "ty_suat_ln_gop": round(tong_gp / tong_nr * 100, 2) if tong_nr else 0,
        "so_don": so_don,
        "aov": aov,
        "so_cua_hang": int(fact["store_key"].nunique()),
        "so_san_pham": int(fact["product_key"].nunique()),
        "so_dong_fact": len(fact),
    }
    (output_dir / "kpi.json").write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"run_at": datetime.now().isoformat(timespec="seconds"), "use_sample": use_sample, "load": counts, "kpi": kpi, "quality": quality_results}
    (output_dir / "pipeline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKPI: DT thuần={tong_nr/1e9:.2f} tỷ | AOV={aov:,.0f} | LN gộp={tong_gp/1e9:.2f} tỷ ({kpi['ty_suat_ln_gop']}%)")
    print("PIPELINE HOÀN TẤT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
