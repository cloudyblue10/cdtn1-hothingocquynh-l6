"""Tạo bộ dữ liệu MẪU nhỏ (data/sample/) từ bộ đầy đủ (data/raw/) — để commit vào Git.

    python scripts/make_sample.py --raw data/raw --out data/sample --orders 1500 --seed 42

* Lấy ngẫu nhiên có hạt giống cố định (seed) => chạy lại ra đúng cùng bộ mẫu.
* CỐ Ý giữ lại các dòng lỗi (ngày trống, tổng tiền dạng văn bản, thành tiền dòng sai)
  để bộ mẫu vẫn minh hoạ được bảng reject và fix_log.
* products.csv và stores.csv nhỏ nên chép nguyên.
"""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/sample"))
    ap.add_argument("--orders", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    orders = pd.read_csv(a.raw / "orders_2024_2026.csv", dtype=str, keep_default_na=False)
    items = pd.read_csv(a.raw / "order_items.csv", dtype=str, keep_default_na=False)
    rng = random.Random(a.seed)

    # Đơn có lỗi cố ý: ngày trống, tổng tiền văn bản/trống, chứa dòng hàng sai thành tiền
    def mismatch(r):
        return r.so_luong.isdigit() and r.don_gia.isdigit() and int(r.so_luong) * int(r.don_gia) != int(r.thanh_tien)

    bad_items = {r.order_id for r in items.itertuples() if mismatch(r)}
    must = (set(orders.loc[orders["ngay"] == "", "order_id"][:15])
            | set(orders.loc[orders["thanh_tien"].str.contains("đ"), "order_id"][:10])
            | set(orders.loc[orders["thanh_tien"] == "", "order_id"][:10])
            | set(sorted(bad_items, key=int)[:20]))
    rest = sorted(set(orders["order_id"]) - must, key=int)
    chosen = must | set(rng.sample(rest, max(0, a.orders - len(must))))

    a.out.mkdir(parents=True, exist_ok=True)
    orders[orders["order_id"].isin(chosen)].to_csv(a.out / "orders_2024_2026.csv", index=False)
    items[items["order_id"].isin(chosen)].to_csv(a.out / "order_items.csv", index=False)
    for name in ("products.csv", "stores.csv"):
        shutil.copy(a.raw / name, a.out / name)
    print(f"Đã tạo bộ mẫu {len(chosen)} đơn tại {a.out} (seed={a.seed}, gồm {len(must)} đơn có lỗi cố ý)")


if __name__ == "__main__":
    main()
