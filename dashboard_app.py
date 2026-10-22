#!/usr/bin/env python3
"""
Dashboard web – Mekong Mobile DWH
Chạy:  python scripts/dashboard_app.py
Mở:    http://127.0.0.1:8050
"""
from __future__ import annotations

import csv
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PORT = int(os.getenv("DASHBOARD_PORT", "8050"))


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_html() -> str:
    kpi = {}
    kpi_path = OUTPUT / "kpi.json"
    if kpi_path.exists():
        kpi = json.loads(kpi_path.read_text(encoding="utf-8"))

    by_month = read_csv(OUTPUT / "doanh_thu_theo_thang.csv")
    by_store = read_csv(OUTPUT / "top_cua_hang.csv")
    by_brand = read_csv(OUTPUT / "top_thuong_hieu.csv")
    by_city = read_csv(OUTPUT / "doanh_thu_theo_tp.csv")

    # empty / error states
    has_data = len(by_month) > 0 or len(by_store) > 0
    state = "ok" if has_data else "empty"

    month_labels = [f"{r.get('year')}-{str(r.get('month')).zfill(2)}" for r in by_month]
    month_values = [round(float(r.get("thanh_tien", 0)) / 1e9, 3) for r in by_month]
    store_labels = [r.get("store_name", "")[:28] for r in by_store][::-1]
    store_values = [round(float(r.get("thanh_tien", 0)) / 1e9, 3) for r in by_store][::-1]
    brand_labels = [r.get("thuong_hieu", "") for r in by_brand]
    brand_values = [round(float(r.get("thanh_tien", 0)) / 1e9, 3) for r in by_brand]
    city_labels = [r.get("thanh_pho", "") for r in by_city]
    city_values = [round(float(r.get("thanh_tien", 0)) / 1e9, 3) for r in by_city]

    tong = kpi.get("tong_doanh_thu", 0)
    tong_str = f"{tong/1e9:.2f} tỷ" if tong else "—"
    so_don = kpi.get("so_don", "—")
    so_ch = kpi.get("so_cua_hang", "—")
    so_sp = kpi.get("so_san_pham", "—")

    data_json = json.dumps(
        {
            "month_labels": month_labels,
            "month_values": month_values,
            "store_labels": store_labels,
            "store_values": store_values,
            "brand_labels": brand_labels,
            "brand_values": brand_values,
            "city_labels": city_labels,
            "city_values": city_values,
            "state": state,
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Mekong Mobile – Dashboard Doanh thu</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --navy: #1a2744;
    --accent: #e67e22;
    --bg: #f0f2f5;
    --card: #ffffff;
    --text: #1a1a2e;
    --muted: #6b7280;
    --green: #10b981;
    --red: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}
  header {{
    background: linear-gradient(135deg, var(--navy) 0%, #2c3e6b 100%);
    color: #fff;
    padding: 20px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 12px rgba(0,0,0,.15);
  }}
  header h1 {{ font-size: 1.35rem; font-weight: 700; }}
  header .sub {{ font-size: .85rem; opacity: .75; margin-top: 4px; }}
  header .badge {{
    background: var(--accent);
    color: #fff;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: .8rem;
    font-weight: 600;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 20px 40px; }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}
  .kpi {{
    background: var(--card);
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    border-left: 4px solid var(--accent);
  }}
  .kpi .label {{ font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .kpi .value {{ font-size: 1.5rem; font-weight: 700; margin-top: 6px; color: var(--navy); }}
  .charts {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }}
  @media (max-width: 800px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: var(--card);
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }}
  .card h2 {{
    font-size: .95rem;
    color: var(--navy);
    margin-bottom: 4px;
  }}
  .card .q {{
    font-size: .8rem;
    color: var(--muted);
    margin-bottom: 12px;
  }}
  .card .src {{
    font-size: .72rem;
    color: var(--muted);
    margin-top: 10px;
  }}
  canvas {{ max-height: 280px; }}
  .state-box {{
    text-align: center;
    padding: 60px 20px;
    background: var(--card);
    border-radius: 12px;
    margin-bottom: 24px;
  }}
  .state-box.empty {{ border: 2px dashed #cbd5e1; }}
  .state-box.error {{ border: 2px solid var(--red); color: var(--red); }}
  .state-box h2 {{ margin-bottom: 8px; }}
  footer {{
    text-align: center;
    padding: 16px;
    font-size: .78rem;
    color: var(--muted);
  }}
  .loading {{
    display: none;
    text-align: center;
    padding: 40px;
    color: var(--muted);
  }}
  .loading.show {{ display: block; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Mekong Mobile – Dashboard Doanh thu</h1>
    <div class="sub">Luồng L6 · Kho dữ liệu bán hàng · Track DA · BT2</div>
  </div>
  <div class="badge">Hồ Thị Ngọc Quỳnh · 2374802010426</div>
</header>

<div class="container">
  <div id="loading" class="loading">Đang truy vấn dữ liệu…</div>

  <div id="state-empty" class="state-box empty" style="display:none">
    <h2>Chưa có dữ liệu</h2>
    <p>Bộ lọc không trả về dòng nào hoặc pipeline chưa chạy.<br/>
    Chạy <code>python scripts/run_pipeline.py</code> rồi tải lại trang.</p>
  </div>

  <div id="state-error" class="state-box error" style="display:none">
    <h2>Lỗi kết nối kho dữ liệu</h2>
    <p>Không đọc được dữ liệu. Kiểm tra file output/ và chạy lại pipeline.<br/>
    <button onclick="location.reload()" style="margin-top:12px;padding:8px 20px;cursor:pointer;border:none;background:var(--red);color:#fff;border-radius:6px">Thử lại</button></p>
  </div>

  <div id="main-content">
    <div class="kpi-row">
      <div class="kpi"><div class="label">Tổng doanh thu</div><div class="value">{tong_str}</div></div>
      <div class="kpi"><div class="label">Số đơn hàng</div><div class="value">{so_don}</div></div>
      <div class="kpi"><div class="label">Số cửa hàng</div><div class="value">{so_ch}</div></div>
      <div class="kpi"><div class="label">Số sản phẩm</div><div class="value">{so_sp}</div></div>
    </div>

    <div class="charts">
      <div class="card">
        <h2>Q1. Doanh thu theo tháng</h2>
        <div class="q">Doanh thu thay đổi thế nào theo thời gian?</div>
        <canvas id="chartMonth"></canvas>
        <div class="src">Nguồn: fact_sales + dim_date · đơn vị: tỷ VNĐ · đường ngang = trung bình tháng</div>
      </div>
      <div class="card">
        <h2>Q2. Top 10 cửa hàng</h2>
        <div class="q">Cửa hàng nào đóng góp doanh thu nhiều nhất?</div>
        <canvas id="chartStore"></canvas>
        <div class="src">Nguồn: fact_sales + dim_store · đơn vị: tỷ VNĐ</div>
      </div>
      <div class="card">
        <h2>Q3. Doanh thu theo thương hiệu</h2>
        <div class="q">Thương hiệu nào bán chạy?</div>
        <canvas id="chartBrand"></canvas>
        <div class="src">Nguồn: fact_sales + dim_product · đơn vị: tỷ VNĐ</div>
      </div>
      <div class="card">
        <h2>Q4. Doanh thu theo thành phố</h2>
        <div class="q">Thị trường nào mạnh nhất?</div>
        <canvas id="chartCity"></canvas>
        <div class="src">Nguồn: fact_sales + dim_store · đơn vị: tỷ VNĐ</div>
      </div>
    </div>
  </div>
</div>

<footer>
  Chuyên đề tốt nghiệp 1 · Trường Đại học Văn Lang · Khoa CNTT · HK1 2026–2027
</footer>

<script>
const DATA = {data_json};

function avg(arr) {{
  if (!arr.length) return 0;
  return arr.reduce((a,b)=>a+b,0) / arr.length;
}}

function showState(state) {{
  document.getElementById("loading").classList.remove("show");
  if (state === "empty") {{
    document.getElementById("state-empty").style.display = "block";
    document.getElementById("main-content").style.display = "none";
  }} else if (state === "error") {{
    document.getElementById("state-error").style.display = "block";
    document.getElementById("main-content").style.display = "none";
  }} else {{
    document.getElementById("main-content").style.display = "block";
  }}
}}

document.getElementById("loading").classList.add("show");

setTimeout(() => {{
  try {{
    if (DATA.state === "empty" || (!DATA.month_values.length && !DATA.store_values.length)) {{
      showState("empty");
      return;
    }}
    showState("ok");

    const meanMonth = avg(DATA.month_values);

    new Chart(document.getElementById("chartMonth"), {{
      type: "bar",
      data: {{
        labels: DATA.month_labels,
        datasets: [
          {{
            label: "Doanh thu (tỷ)",
            data: DATA.month_values,
            backgroundColor: "rgba(26,39,68,0.75)",
            borderRadius: 4,
          }},
          {{
            label: "TB tháng",
            data: DATA.month_values.map(() => meanMonth),
            type: "line",
            borderColor: "#e67e22",
            borderWidth: 2,
            borderDash: [6,4],
            pointRadius: 0,
            fill: false,
          }}
        ]
      }},
      options: {{
        responsive: true,
        plugins: {{ legend: {{ position: "top" }} }},
        scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: "Tỷ VNĐ" }} }} }}
      }}
    }});

    new Chart(document.getElementById("chartStore"), {{
      type: "bar",
      data: {{
        labels: DATA.store_labels,
        datasets: [{{
          label: "Doanh thu (tỷ)",
          data: DATA.store_values,
          backgroundColor: "rgba(16,185,129,0.75)",
          borderRadius: 4,
        }}]
      }},
      options: {{
        indexAxis: "y",
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ beginAtZero: true, title: {{ display: true, text: "Tỷ VNĐ" }} }} }}
      }}
    }});

    new Chart(document.getElementById("chartBrand"), {{
      type: "doughnut",
      data: {{
        labels: DATA.brand_labels,
        datasets: [{{
          data: DATA.brand_values,
          backgroundColor: [
            "#1a2744","#e67e22","#10b981","#3b82f6","#8b5cf6","#f59e0b","#ef4444","#06b6d4"
          ],
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{ legend: {{ position: "right" }} }}
      }}
    }});

    new Chart(document.getElementById("chartCity"), {{
      type: "bar",
      data: {{
        labels: DATA.city_labels,
        datasets: [{{
          label: "Doanh thu (tỷ)",
          data: DATA.city_values,
          backgroundColor: "rgba(59,130,246,0.75)",
          borderRadius: 4,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: "Tỷ VNĐ" }} }} }}
      }}
    }});
  }} catch (e) {{
    console.error(e);
    showState("error");
  }}
}}, 400);
</script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html", "/dashboard"):
            html = build_html()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    # luôn ghi sẵn 1 bản HTML tĩnh để mở offline
    html_path = OUTPUT / "dashboard.html"
    html_path.write_text(build_html(), encoding="utf-8")
    print(f"Đã ghi {html_path}")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 50)
    print("  MEKONG MOBILE – DASHBOARD DOANH THU")
    print(f"  Mở trình duyệt: http://127.0.0.1:{PORT}")
    print("  Nhấn Ctrl+C để dừng")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng dashboard.")
        server.server_close()


if __name__ == "__main__":
    main()
