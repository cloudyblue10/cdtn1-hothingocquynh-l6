/* BA TRẠNG THÁI bắt buộc của mọi khung dữ liệu: ĐANG TẢI · RỖNG · LỖI. */
const States = (() => {
  /** Đang tải: khung xương giữ bố cục để người dùng biết hệ thống đang truy vấn. */
  function loading(el, { kpis = 4, charts = 2, text = "Đang truy vấn kho dữ liệu…" } = {}) {
    const k = Array.from({ length: kpis }, () =>
      `<div class="card"><div class="sk sk-line" style="width:45%"></div><div class="sk sk-big"></div><div class="sk sk-line" style="width:70%"></div></div>`).join("");
    const c = Array.from({ length: charts }, () =>
      `<div class="card"><div class="sk sk-line" style="width:35%"></div><div class="sk sk-line" style="width:60%"></div><div class="sk sk-chart"></div></div>`).join("");
    el.innerHTML = `<p class="loading-text" role="status">⏳ ${Fmt.esc(text)}</p>
      ${kpis ? `<div class="grid kpis">${k}</div>` : ""}
      <div class="grid ${charts > 1 ? "two" : ""}">${c}</div>`;
    el.setAttribute("aria-busy", "true");
  }

  /** Rỗng: phân biệt "kho chưa có dữ liệu" và "bộ lọc không ra dòng nào". */
  function empty(el, status, { filterLabel = "", onReset = null } = {}) {
    el.removeAttribute("aria-busy");
    const isWarehouse = status === "empty_warehouse";
    const title = isWarehouse ? "Kho dữ liệu chưa có dữ liệu" : "Không tìm thấy dữ liệu giao dịch trong khoảng thời gian này";
    const msg = isWarehouse
      ? "Pipeline chưa nạp đơn hàng nào vào kho. Chạy <code>python -m src.pipeline</code> rồi tải lại trang."
      : `Bộ lọc <strong>${Fmt.esc(filterLabel)}</strong> không khớp đơn hàng nào. Thử chọn khoảng thời gian rộng hơn hoặc bỏ lọc cửa hàng/danh mục.`;
    el.innerHTML = `<div class="state empty" data-state="${isWarehouse ? "empty-warehouse" : "empty-filter"}">
      <div class="icon" aria-hidden="true">∅</div><h3>${title}</h3><p>${msg}</p>
      <div class="actions">${!isWarehouse && onReset ? `<button class="btn primary" data-act="reset">Về tháng gần nhất có dữ liệu</button>` : ""}
      ${isWarehouse ? `<button class="btn" data-act="reload">Tải lại</button>` : ""}</div></div>`;
    el.querySelector('[data-act="reset"]')?.addEventListener("click", onReset);
    el.querySelector('[data-act="reload"]')?.addEventListener("click", () => location.reload());
  }

  /** Lỗi: chuyện gì · vì sao / làm gì tiếp · nút Thử lại (+ mã tra cứu nếu có). */
  function error(el, err, onRetry) {
    el.removeAttribute("aria-busy");
    const title = {
      network: "Mất kết nối tới máy chủ",
      warehouse: "Không thể kết nối tới Kho dữ liệu",
      validation: "Bộ lọc chưa hợp lệ",
      server: "Hệ thống gặp sự cố",
    }[err.kind] || "Có lỗi xảy ra";
    el.innerHTML = `<div class="state error" data-state="error" role="alert">
      <div class="icon" aria-hidden="true">!</div><h3>${title}</h3>
      <p>${Fmt.esc(err.message)}</p><p>${Fmt.esc(err.hint || "")}</p>
      ${err.ref ? `<p class="ref">Mã tra cứu: ${Fmt.esc(err.ref)}</p>` : ""}
      <div class="actions"><button class="btn primary" data-act="retry">Thử lại</button></div></div>`;
    el.querySelector('[data-act="retry"]').addEventListener("click", onRetry);
  }

  return { loading, empty, error };
})();
