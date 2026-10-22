#!/usr/bin/env python3
"""
Dashboard phân tích doanh thu – ≥ 2 biểu đồ, mỗi biểu đồ gắn câu hỏi phân tích.
Xử lý 3 trạng thái: đang truy vấn / rỗng / lỗi kết nối.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.load import get_engine


def query_df(engine, sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def main():
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    status = "ok"
    message = ""

    try:
        engine = get_engine()
        # kiểm tra bảng tồn tại
        with engine.connect() as conn:
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        table_names = {t[0] for t in tables}
        if "fact_sales" not in table_names:
            status = "empty"
            message = "Chưa có dữ liệu fact_sales. Hãy chạy pipeline trước: python scripts/run_pipeline.py"
    except Exception as e:
        status = "error"
        message = f"Lỗi kết nối kho dữ liệu: {type(e).__name__}. Kiểm tra DATABASE_URL trong .env"

    if status == "error":
        print(f"[ERROR] {message}")
        # vẫn tạo ảnh placeholder lỗi
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True, color="red")
        ax.axis("off")
        fig.savefig(output_dir / "dashboard_error.png", dpi=120, bbox_inches="tight")
        plt.close()
        return 1

    if status == "empty":
        print(f"[EMPTY] {message}")
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
        ax.axis("off")
        fig.savefig(output_dir / "dashboard_empty.png", dpi=120, bbox_inches="tight")
        plt.close()
        return 0

    # ---- Câu hỏi 1: Doanh thu theo tháng ----
    print("[QUERY] Doanh thu theo tháng...")
    df_month = query_df(
        engine,
        """
        SELECT d.year, d.month,
               SUM(f.thanh_tien) AS doanh_thu,
               SUM(f.so_luong) AS so_luong
        FROM fact_sales f
        JOIN dim_date d ON f.sk_date = d.sk_date
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
        """,
    )

    # ---- Câu hỏi 2: Top cửa hàng theo doanh thu ----
    print("[QUERY] Top cửa hàng...")
    df_store = query_df(
        engine,
        """
        SELECT s.store_name, s.thanh_pho,
               SUM(f.thanh_tien) AS doanh_thu
        FROM fact_sales f
        JOIN dim_store s ON f.sk_store = s.sk_store
        GROUP BY s.store_name, s.thanh_pho
        ORDER BY doanh_thu DESC
        LIMIT 10
        """,
    )

    if len(df_month) == 0 and len(df_store) == 0:
        print("[EMPTY] Bộ lọc không trả về dòng nào.")
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "Bộ lọc không trả về dòng nào.", ha="center", va="center")
        ax.axis("off")
        fig.savefig(output_dir / "dashboard_empty.png", dpi=120, bbox_inches="tight")
        plt.close()
        return 0

    # ---- Vẽ biểu đồ ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Biểu đồ 1
    if len(df_month) > 0:
        df_month["label"] = df_month["year"].astype(str) + "-" + df_month["month"].astype(str).str.zfill(2)
        avg = df_month["doanh_thu"].mean()
        axes[0].bar(df_month["label"], df_month["doanh_thu"] / 1e9, color="steelblue")
        axes[0].axhline(avg / 1e9, color="orange", linestyle="--", label=f"TB tháng: {avg/1e9:.2f} tỷ")
        axes[0].set_title("Q1. Doanh thu theo tháng (tỷ VNĐ)")
        axes[0].set_xlabel("Tháng")
        axes[0].set_ylabel("Doanh thu (tỷ)")
        axes[0].tick_params(axis="x", rotation=45)
        axes[0].legend()
        axes[0].text(
            0.01, 0.98,
            f"Nguồn: fact_sales · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            transform=axes[0].transAxes, fontsize=8, va="top",
        )
    else:
        axes[0].text(0.5, 0.5, "Không có dữ liệu theo tháng", ha="center")
        axes[0].axis("off")

    # Biểu đồ 2
    if len(df_store) > 0:
        axes[1].barh(df_store["store_name"][::-1], df_store["doanh_thu"][::-1] / 1e9, color="seagreen")
        axes[1].set_title("Q2. Top 10 cửa hàng theo doanh thu (tỷ VNĐ)")
        axes[1].set_xlabel("Doanh thu (tỷ)")
        top1 = df_store.iloc[0]["doanh_thu"]
        axes[1].axvline(top1 / 1e9, color="red", linestyle=":", alpha=0.5, label="Top 1")
        axes[1].legend()
        axes[1].text(
            0.01, 0.98,
            f"Nguồn: fact_sales + dim_store · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            transform=axes[1].transAxes, fontsize=8, va="top",
        )
    else:
        axes[1].text(0.5, 0.5, "Không có dữ liệu cửa hàng", ha="center")
        axes[1].axis("off")

    plt.tight_layout()
    out_path = output_dir / "dashboard_revenue.png"
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"[OK] Đã lưu {out_path}")

    # xuất số liệu CSV kèm
    df_month.to_csv(output_dir / "doanh_thu_theo_thang.csv", index=False)
    df_store.to_csv(output_dir / "top_cua_hang.csv", index=False)
    print("[OK] Đã xuất CSV số liệu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
