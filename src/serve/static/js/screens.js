/* Bốn màn hình của dashboard. Mỗi màn hình có:
 *   fetch(filters, extra) -> Promise<data>   (chỉ gọi qua lớp Api)
 *   render(el, data, ctx)                     (chỉ vẽ trạng thái CÓ DỮ LIỆU)
 * Trạng thái đang tải / rỗng / lỗi do app.js + states.js đảm nhiệm. */
const Screens = (() => {
  const src = (s, extra = "") =>
    `<p class="src">Nguồn: ${Fmt.esc(s.tables)} · lần nạp ${Fmt.esc(s.run_id || "—")} lúc ${Fmt.dateTime(s.updated_at)}${extra}</p>`;

  function kpiCard(label, value, k, prevLabel, unit = "%") {
    return `<div class="card kpi"><div class="label">${label}</div><div class="value">${value}</div>
      <div class="cmp">${Fmt.delta(k.delta_pct ?? k.delta_pt, unit)} so với kỳ trước<br>
      <span>Kỳ trước (${prevLabel}): ${k.prevText}</span></div></div>`;
  }

  /* ======================= 1. TỔNG QUAN ======================= */
  const overview = {
    fetch: (f) => Api.overview(f),
    render(el, d) {
      const k = d.kpis, pl = `${Fmt.date(d.previous_filter.from)}–${Fmt.date(d.previous_filter.to)}`;
      const cards = [
        kpiCard("Doanh thu thuần", Fmt.vnd(k.net_revenue.value), { ...k.net_revenue, prevText: Fmt.vnd(k.net_revenue.previous) }, pl),
        kpiCard("Số đơn hàng", Fmt.int(k.orders.value), { ...k.orders, prevText: Fmt.int(k.orders.previous) }, pl),
        kpiCard("Giá trị trung bình đơn (AOV)", Fmt.vnd(k.aov.value), { ...k.aov, prevText: Fmt.vnd(k.aov.previous) }, pl),
        kpiCard("Lợi nhuận gộp (ước tính)", `${Fmt.vnd(k.gross_profit.value)} <small style="font-size:13px;color:var(--muted)">· ${Fmt.pct(k.margin_pct.value)}</small>`,
          { ...k.gross_profit, prevText: `${Fmt.vnd(k.gross_profit.previous)} · ${Fmt.pct(k.margin_pct.previous)}` }, pl),
      ].join("");
      const alerts = d.alerts.items.length
        ? `<div class="table-wrap"><table><thead><tr><th>Ngày</th><th class="num">Doanh thu</th><th class="num">TB 7 ngày trước</th><th class="num">Lệch</th></tr></thead><tbody>
          ${d.alerts.items.slice().reverse().map((a) => `<tr><td>${Fmt.date(a.day)}</td><td class="num">${Fmt.vnd(a.net_revenue)}</td>
          <td class="num">${Fmt.vnd(a.baseline)}</td><td class="num"><span class="pill ${a.change_pct > 0 ? "good" : "bad"}">${a.change_pct > 0 ? "▲" : "▼"} ${Fmt.pct(Math.abs(a.change_pct))}</span></td></tr>`).join("")}
          </tbody></table></div>`
        : `<p class="q">Không có ngày nào lệch quá ${d.alerts.threshold_pct}% so với trung bình 7 ngày liền trước.</p>`;

      el.innerHTML = `<div class="grid kpis">${cards}</div>
        <div class="grid two">
          <section class="card">
            <h2>Doanh thu thuần theo ngày</h2>
            <p class="q">Câu hỏi: doanh thu từng ngày cao hay thấp hơn mức trung bình của kỳ, ngày nào bất thường?</p>
            <div class="legend"><span><i style="background:var(--series-1)"></i>Doanh thu thuần</span>
              <span><i class="dash"></i>Trung bình ngày của kỳ (${Fmt.vnd(d.daily_avg_revenue)})</span>
              <span><i style="background:var(--series-2);height:8px;width:8px;border-radius:50%"></i>Ngày bị cảnh báo</span></div>
            <div id="ch-daily"></div>
            ${src(d.source)}
          </section>
          <section class="card">
            <h2>Cảnh báo biến động doanh thu &gt; ${d.alerts.threshold_pct}%</h2>
            <p class="q">So với trung bình 7 ngày liền trước (FR-11) · ${d.alerts.count} ngày trong kỳ</p>
            ${alerts}
          </section>
        </div>
        <div class="grid" style="margin-top:16px">
          <section class="card">
            <h2>Số đơn hàng theo ngày</h2>
            <p class="q">Câu hỏi: lượng đơn mỗi ngày có ổn định quanh mức trung bình không?</p>
            <div id="ch-orders"></div>
            ${src(d.source)}
          </section>
        </div>`;

      const pts = d.daily.map((r) => ({ key: r.day, label: Fmt.date(r.day).slice(0, 5), y: r.net_revenue, orders: r.orders }));
      Charts.line(document.getElementById("ch-daily"), {
        points: pts, refValue: d.daily_avg_revenue, refLabel: "TB " + Fmt.vnd(d.daily_avg_revenue),
        highlights: d.alerts.items.map((a) => a.day), ariaLabel: "Doanh thu thuần theo ngày",
        tipFmt: (p) => `<b>${Fmt.date(p.key)}</b><br>Doanh thu: ${Fmt.vndFull(p.y)}<br>Số đơn: ${Fmt.int(p.orders)}`,
      });
      const avgOrders = d.daily.reduce((s, r) => s + r.orders, 0) / d.daily.length;
      Charts.columns(document.getElementById("ch-orders"), {
        items: d.daily.map((r) => ({ label: Fmt.date(r.day).slice(0, 5), value: r.orders, day: r.day })),
        refValue: avgOrders, refLabel: `TB ${avgOrders.toFixed(1)} đơn/ngày`, yFmt: (v) => Fmt.int(v),
        ariaLabel: "Số đơn theo ngày", tipFmt: (it) => `<b>${Fmt.date(it.day)}</b><br>${it.value} đơn`,
      });
    },
  };

  /* ======================= 2. SẢN PHẨM & CỬA HÀNG ======================= */
  const products = {
    async fetch(f, x) {
      const [p, s] = await Promise.all([Api.products({ ...f, sort: x.sort, q: x.q }), Api.stores(f)]);
      // Rỗng khi KHÔNG có giao dịch; tìm kiếm không khớp vẫn hiển thị màn hình với bảng rỗng
      const status = p.status === "ok" || p.search ? s.status : p.status;
      return { status, filter: s.filter, p, s };
    },
    render(el, d, ctx) {
      const { p, s } = d;
      const top = p.rows.slice(0, 10);
      const avgProduct = p.rows.length ? p.total_revenue / p.rows.length : 0;
      const metric = p.sort === "quantity" ? "quantity" : "net_revenue";
      const rows = p.rows.length
        ? p.rows.map((r) => `<tr class="${r.is_top10 ? "top10" : ""}"><td>${Fmt.esc(r.product_code)}</td><td>${Fmt.esc(r.product_name)}</td>
            <td>${Fmt.esc(r.category_name)}</td><td class="num">${Fmt.int(r.quantity)}</td><td class="num">${Fmt.vnd(r.net_revenue)}</td>
            <td class="num">${Fmt.vnd(r.cogs_amount)}</td><td class="num">${Fmt.vnd(r.gross_profit)}</td>
            <td class="num">${Fmt.pct(r.margin_pct)}</td><td class="num">${Fmt.pct(r.share_pct, 2)}</td></tr>`).join("")
        : `<tr><td colspan="9"><div class="state empty" style="padding:20px"><h3>Không có sản phẩm khớp “${Fmt.esc(p.search || "")}”</h3>
            <p>Thử từ khoá khác (mã như SS0002 hoặc tên như “Pro Max”).</p></div></td></tr>`;

      el.innerHTML = `<div class="grid half">
          <section class="card">
            <h2>Top 10 sản phẩm theo ${metric === "quantity" ? "số lượng bán" : "doanh thu thuần"}</h2>
            <p class="q">Câu hỏi: mặt hàng nào đóng góp nhiều nhất, cao gấp bao nhiêu lần mức trung bình một sản phẩm?</p>
            <div id="ch-top"></div>
            ${src(p.source)}
          </section>
          <section class="card">
            <h2>Doanh thu theo cửa hàng (${s.rows.length} cửa hàng)</h2>
            <p class="q">Câu hỏi: cửa hàng nào trên / dưới mức trung bình của chuỗi?</p>
            <div id="ch-store"></div>
            ${src(s.source, " · bộ lọc cửa hàng không áp dụng cho biểu đồ so sánh này")}
          </section>
        </div>
        <section class="card" style="margin-top:16px">
          <h2>Bảng chi tiết sản phẩm</h2>
          <p class="q">Tô xanh = Top 10 · Tỷ trọng = doanh thu sản phẩm ÷ tổng doanh thu trong bộ lọc (${Fmt.vnd(p.total_revenue)}) · tỷ suất LN gộp chung ${Fmt.pct(p.overall_margin_pct)}</p>
          <div class="toolbar">
            <input id="p-search" placeholder="Tìm mã hoặc tên sản phẩm…" value="${Fmt.esc(p.search || "")}" maxlength="60">
            <select id="p-sort"><option value="revenue" ${p.sort === "revenue" ? "selected" : ""}>Sắp theo doanh thu</option>
              <option value="quantity" ${p.sort === "quantity" ? "selected" : ""}>Sắp theo số lượng</option></select>
            <button class="btn" id="p-go">Lọc bảng</button>
          </div>
          <div class="table-wrap scroll"><table><thead><tr><th>Mã SP</th><th>Tên sản phẩm</th><th>Danh mục</th><th class="num">SL bán</th>
            <th class="num">Doanh thu</th><th class="num">Giá vốn</th><th class="num">LN gộp</th><th class="num">Tỷ suất</th><th class="num">Tỷ trọng</th></tr></thead>
            <tbody>${rows}</tbody></table></div>
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Theo danh mục</h2>
          <div class="table-wrap"><table><thead><tr><th>Danh mục</th><th class="num">SL bán</th><th class="num">Doanh thu</th>
          <th class="num">LN gộp</th><th class="num">Tỷ suất</th><th class="num">Tỷ trọng</th></tr></thead><tbody>
          ${p.categories.map((c) => `<tr><td>${Fmt.esc(c.category_name)}</td><td class="num">${Fmt.int(c.quantity)}</td><td class="num">${Fmt.vnd(c.net_revenue)}</td>
            <td class="num">${Fmt.vnd(c.gross_profit)}</td><td class="num">${Fmt.pct(c.margin_pct)}</td><td class="num">${Fmt.pct(c.share_pct, 2)}</td></tr>`).join("")}
          </tbody></table></div>
        </section>`;

      if (top.length) {
        const avgQty = p.rows.length ? p.rows.reduce((a, r) => a + r.quantity, 0) / p.rows.length : 0;
        Charts.hbar(document.getElementById("ch-top"), {
          items: top.map((r) => ({ label: r.product_name, value: r[metric], r })), labelWidth: 190,
          refValue: metric === "quantity" ? avgQty : avgProduct,
          refLabel: metric === "quantity" ? `TB ${avgQty.toFixed(1)} sp` : "TB/sản phẩm " + Fmt.vnd(avgProduct),
          valueFmt: metric === "quantity" ? (v) => Fmt.int(v) : Fmt.vnd, ariaLabel: "Top 10 sản phẩm",
          tipFmt: (it) => `<b>${Fmt.esc(it.r.product_code)} · ${Fmt.esc(it.r.product_name)}</b><br>Doanh thu: ${Fmt.vndFull(it.r.net_revenue)}<br>SL: ${it.r.quantity} · Tỷ trọng ${Fmt.pct(it.r.share_pct, 2)}`,
        });
      } else {
        document.getElementById("ch-top").innerHTML = `<p class="q">Không có sản phẩm khớp từ khoá — biểu đồ trống.</p>`;
      }
      Charts.hbar(document.getElementById("ch-store"), {
        items: s.rows.map((r) => ({ label: r.store_name.replace("Mekong Mobile ", ""), value: r.net_revenue, highlight: ctx.filters.store === r.store_code, r })),
        refValue: s.avg_revenue, refLabel: "TB chuỗi " + Fmt.vnd(s.avg_revenue), labelWidth: 130, ariaLabel: "Doanh thu theo cửa hàng",
        tipFmt: (it) => `<b>${Fmt.esc(it.r.store_code)} · ${Fmt.esc(it.r.store_name)}</b><br>${Fmt.esc(it.r.city)}<br>Doanh thu: ${Fmt.vndFull(it.r.net_revenue)}<br>
          So với TB chuỗi: ${it.r.vs_avg_pct > 0 ? "+" : ""}${Fmt.pct(it.r.vs_avg_pct)} · so với kỳ trước: ${it.r.delta_pct === null ? "—" : (it.r.delta_pct > 0 ? "+" : "") + Fmt.pct(it.r.delta_pct)}`,
      });

      const go = () => ctx.setExtra({ q: document.getElementById("p-search").value.trim(), sort: document.getElementById("p-sort").value });
      document.getElementById("p-go").addEventListener("click", go);
      document.getElementById("p-sort").addEventListener("change", go);
      document.getElementById("p-search").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
    },
  };

  /* ======================= 3. KÊNH & THANH TOÁN ======================= */
  const payments = {
    fetch: (f) => Api.payments(f),
    render(el, d) {
      el.innerHTML = `<p class="note">ⓘ ${Fmt.esc(d.channel_note)} Phương thức thanh toán được suy ra từ ghi chú đơn
          (“Trả góp 0%” → Trả góp; còn lại → Trả thẳng) — xem docs/thay-doi-thiet-ke.md.</p>
        <div class="grid half">
          <section class="card">
            <h2>Tỷ trọng doanh thu trả góp theo tháng</h2>
            <p class="q">Câu hỏi: tỷ trọng trả góp tháng nào cao hơn mức trung bình của giai đoạn? ${d.installment_trend.length < 3 ? "<br><b>Mẹo:</b> chọn “Toàn bộ” hoặc khoảng ≥ 3 tháng để thấy xu hướng." : ""}</p>
            <div id="ch-inst"></div>
            ${src(d.source)}
          </section>
          <section class="card">
            <h2>Doanh thu theo phương thức thanh toán</h2>
            <p class="q">Câu hỏi: cơ cấu thanh toán kỳ này thay đổi thế nào so với kỳ trước?</p>
            <div id="ch-pay"></div>
            <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Phương thức</th><th>Kênh</th><th class="num">Số đơn</th>
              <th class="num">Doanh thu</th><th class="num">Tỷ trọng</th><th class="num">Kỳ trước</th><th class="num">AOV</th></tr></thead><tbody>
              ${d.rows.map((r) => `<tr><td>${Fmt.esc(r.payment_method)}</td><td>${Fmt.esc(r.channel_name)}</td><td class="num">${Fmt.int(r.orders)}</td>
                <td class="num">${Fmt.vnd(r.net_revenue)}</td><td class="num">${Fmt.pct(r.share_pct)}</td>
                <td class="num">${r.prev_share_pct === null || r.prev_share_pct === undefined ? "—" : Fmt.pct(r.prev_share_pct)}</td><td class="num">${Fmt.vnd(r.aov)}</td></tr>`).join("")}
            </tbody></table></div>
            ${src(d.source)}
          </section>
        </div>`;
      Charts.columns(document.getElementById("ch-inst"), {
        items: d.installment_trend.map((t) => ({ label: t.month.slice(5) + "/" + t.month.slice(2, 4), value: t.installment_share_pct, month: t.month,
          highlight: t.installment_share_pct > d.installment_avg_share_pct })),
        refValue: d.installment_avg_share_pct, refLabel: "TB " + Fmt.pct(d.installment_avg_share_pct), yFmt: (v) => Fmt.pct(v),
        ariaLabel: "Tỷ trọng trả góp theo tháng", tipFmt: (it) => `<b>Tháng ${it.month.slice(5)}/${it.month.slice(0, 4)}</b><br>Trả góp: ${Fmt.pct(it.value, 2)} doanh thu`,
      });
      Charts.hbar(document.getElementById("ch-pay"), {
        items: d.rows.map((r) => ({ label: r.payment_method, value: r.net_revenue, highlight: r.payment_code === "TRA_GOP", r })),
        labelWidth: 140, ariaLabel: "Doanh thu theo phương thức thanh toán",
        tipFmt: (it) => `<b>${Fmt.esc(it.r.payment_method)}</b><br>${Fmt.vndFull(it.r.net_revenue)} · ${Fmt.pct(it.r.share_pct)}<br>Kỳ trước: ${it.r.prev_share_pct == null ? "—" : Fmt.pct(it.r.prev_share_pct)}`,
      });
    },
  };

  /* ======================= 4. CHẤT LƯỢNG DỮ LIỆU ======================= */
  const quality = {
    fetch: (_f, x) => Api.quality({ rule: x.rule }),
    render(el, d, ctx) {
      const r = d.latest_success, pv = d.previous_success;
      const latest = d.latest_run;
      const ok = r.valid_rate >= d.threshold_pct;
      const banner = latest.status === "SUCCESS"
        ? `<span class="pill good">THÀNH CÔNG</span> Lần chạy gần nhất ${Fmt.esc(latest.run_id)} lúc ${Fmt.dateTime(latest.finished_at)}`
        : `<span class="pill bad">THẤT BẠI</span> ${Fmt.esc(latest.run_id)}: ${Fmt.esc(latest.error_message || "")} — kho vẫn giữ dữ liệu của lần thành công ${Fmt.esc(r.run_id)}`;
      const card = (label, val, cmp) => `<div class="card kpi"><div class="label">${label}</div><div class="value">${val}</div><div class="cmp">${cmp}</div></div>`;
      const prevTxt = (key, f = Fmt.int) => (pv ? `Lần trước: ${f(pv[key])}` : "Chưa có lần chạy trước để so");
      const ruleOpts = d.checks.map((c) => `<option value="${c.rule_code}" ${d.rule_filter === c.rule_code ? "selected" : ""}>${c.rule_code} · ${Fmt.esc(c.rule_name)}</option>`).join("");

      el.innerHTML = `<p class="note" style="background:var(--surface);border:1px solid var(--border)">${banner}</p>
        <div class="grid kpis">
          ${card("Số dòng trích xuất", Fmt.int(r.rows_extracted), prevTxt("rows_extracted"))}
          ${card("Số dòng đã nạp", Fmt.int(r.rows_loaded), prevTxt("rows_loaded"))}
          ${card("Số dòng bị loại", Fmt.int(r.rows_rejected), `${prevTxt("rows_rejected")} · đã sửa tự động ${Fmt.int(r.rows_fixed)}`)}
          ${card("Tỉ lệ hợp lệ", Fmt.pct(r.valid_rate, 2), `<span class="pill ${ok ? "good" : "bad"}">${ok ? "ĐẠT" : "KHÔNG ĐẠT"}</span> ngưỡng ≥ ${d.threshold_pct}%`)}
        </div>
        <div class="grid two">
          <section class="card">
            <h2>Tỉ lệ lỗi theo quy tắc chất lượng</h2>
            <p class="q">Câu hỏi: quy tắc nào phát hiện nhiều lỗi nhất và có vượt ngưỡng cho phép không?</p>
            <div id="ch-rules"></div>
            <p class="src">Nguồn: quality_result (lần chạy ${Fmt.esc(r.run_id)}) · Tỉ lệ hợp lệ = dòng đã nạp ÷ dòng trích xuất × 100</p>
          </section>
          <section class="card">
            <h2>Các lần chạy gần đây</h2>
            <div class="table-wrap"><table><thead><tr><th>Mã lần chạy</th><th>Bắt đầu</th><th>Trạng thái</th><th class="num">Nạp</th><th class="num">Loại</th><th class="num">Fact sau nạp</th></tr></thead><tbody>
            ${d.runs.map((x) => `<tr><td>${Fmt.esc(x.run_id)}</td><td>${Fmt.dateTime(x.started_at)}</td>
              <td><span class="pill ${x.status === "SUCCESS" ? "good" : "bad"}" title="${Fmt.esc(x.error_message || "")}">${x.status}</span></td>
              <td class="num">${Fmt.int(x.rows_loaded)}</td><td class="num">${Fmt.int(x.rows_rejected)}</td><td class="num">${Fmt.int(x.fact_rows_after)}</td></tr>`).join("")}
            </tbody></table></div>
            <p class="src">Nguồn: etl_run_log (append-only). Cột “Fact sau nạp” không đổi giữa các lần chạy cùng nguồn ⇒ nạp lại không nhân đôi.</p>
          </section>
        </div>
        <section class="card" style="margin-top:16px">
          <h2>Bảng kiểm chất lượng (10 quy tắc)</h2>
          <div class="table-wrap"><table><thead><tr><th>Mã</th><th>Quy tắc</th><th>Tệp</th><th class="num">Dòng kiểm</th><th class="num">Dòng lỗi</th>
            <th class="num">Tỉ lệ lỗi</th><th class="num">Ngưỡng</th><th>Xử lý</th><th>Kết luận</th></tr></thead><tbody>
          ${d.checks.map((c) => `<tr><td>${c.rule_code}</td><td>${Fmt.esc(c.rule_name)}</td><td>${Fmt.esc(c.source_file)}</td>
            <td class="num">${Fmt.int(c.rows_checked)}</td><td class="num">${Fmt.int(c.rows_failed)}</td><td class="num">${Fmt.pct(c.fail_rate, 2)}</td>
            <td class="num">≤ ${Fmt.pct(c.max_fail_rate)}</td><td>${{ LOAI: "Loại → reject", SUA: "Sửa → fix_log", GHI_NHAN: "Chỉ ghi nhận" }[c.action]}</td>
            <td><span class="pill ${c.passed ? "good" : "bad"}">${c.passed ? "ĐẠT" : "VƯỢT NGƯỠNG"}</span></td></tr>`).join("")}
          </tbody></table></div>
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Dòng bị loại (bảng reject_records)</h2>
          <p class="q">Tổng: ${d.reject_counts.map((x) => `${x.rule_code} = ${Fmt.int(x.n)}`).join(" · ") || "0"} · hiển thị tối đa 50 dòng</p>
          <div class="toolbar"><select id="q-rule"><option value="">Tất cả quy tắc</option>${ruleOpts}</select></div>
          ${d.rejects.length ? `<div class="table-wrap scroll"><table><thead><tr><th>Tệp nguồn</th><th class="num">Dòng nguồn</th><th>Mã quy tắc</th><th>Cột</th><th>Giá trị gốc</th><th>Lý do</th></tr></thead><tbody>
            ${d.rejects.map((x) => `<tr><td>${Fmt.esc(x.source_file)}</td><td class="num">${x.row_number}</td><td>${x.rule_code}</td><td>${Fmt.esc(x.field_name)}</td>
              <td>${x.raw_value === null ? "<i>(trống)</i>" : Fmt.esc(x.raw_value)}</td><td style="white-space:normal">${Fmt.esc(x.reason)}</td></tr>`).join("")}
            </tbody></table></div>`
            : `<div class="state empty" style="padding:20px"><h3>Không có dòng nào bị loại theo quy tắc ${Fmt.esc(d.rule_filter || "")}</h3><p>Quy tắc này không phát hiện lỗi ở dữ liệu nguồn hiện tại.</p></div>`}
        </section>`;

      Charts.hbar(document.getElementById("ch-rules"), {
        items: d.checks.map((c) => ({ label: `${c.rule_code} ${c.rule_name}`, value: c.fail_rate, highlight: !c.passed, c })),
        valueFmt: (v) => Fmt.pct(v, 2), labelWidth: 230, ariaLabel: "Tỉ lệ lỗi theo quy tắc",
        tipFmt: (it) => `<b>${it.c.rule_code} · ${Fmt.esc(it.c.rule_name)}</b><br>${it.c.rows_failed}/${it.c.rows_checked} dòng = ${Fmt.pct(it.c.fail_rate, 3)}<br>Ngưỡng cho phép ≤ ${it.c.max_fail_rate}%`,
      });
      document.getElementById("q-rule").addEventListener("change", (e) => ctx.setExtra({ rule: e.target.value }));
    },
  };

  return { overview, products, payments, quality };
})();
