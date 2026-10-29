/* Điều phối dashboard: bộ lọc, chuyển màn hình, và gắn BA TRẠNG THÁI cho mỗi lần tải. */
(() => {
  const main = document.getElementById("screen");
  const form = document.getElementById("filters");
  const errBox = document.getElementById("filter-error");
  const badge = document.getElementById("source-badge");
  const S = { screen: "overview", meta: null, filters: {}, extra: { q: "", sort: "revenue", rule: "" }, req: 0 };

  const iso = (d) => d.toISOString().slice(0, 10);
  const addDays = (isoStr, n) => { const d = new Date(isoStr + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return iso(d); };

  function readForm() {
    const fd = new FormData(form);
    return { from: fd.get("from"), to: fd.get("to"), store: fd.get("store"), category: fd.get("category") };
  }
  function writeForm(f) {
    form.from.value = f.from || ""; form.to.value = f.to || "";
    form.store.value = f.store || ""; form.category.value = f.category || "";
  }
  function clearFieldError() {
    errBox.hidden = true;
    form.querySelectorAll(".invalid").forEach((n) => n.classList.remove("invalid"));
  }

  function presetRange(name) {
    const { min_date: min, max_date: max } = S.meta;
    if (name === "all") return { from: min, to: max };
    if (name === "last_7") return { from: addDays(max, -6), to: max };
    if (name === "last_90") return { from: addDays(max, -89), to: max };
    return { from: max.slice(0, 8) + "01", to: max };                 // tháng gần nhất có dữ liệu
  }

  function resetFilters() {
    S.filters = { ...presetRange("last_month"), store: "", category: "" };
    writeForm(S.filters);
    load();
  }

  /* -------- tải một màn hình: ĐANG TẢI → (RỖNG | CÓ DỮ LIỆU | LỖI) -------- */
  async function load() {
    const my = ++S.req;
    S.last = null;                                   // bỏ qua phản hồi cũ nếu người dùng bấm liên tục
    const screen = Screens[S.screen];
    clearFieldError();
    form.classList.toggle("disabled", S.screen === "quality");
    States.loading(main, S.screen === "quality" ? { kpis: 4, charts: 2, text: "Đang đọc nhật ký nạp và bảng reject…" } : {});
    try {
      const data = await screen.fetch(S.filters, S.extra);
      if (my !== S.req) return;
      if (data.status !== "ok") {
        States.empty(main, data.status, { filterLabel: data.filter?.label || "", onReset: resetFilters });
        return;
      }
      main.removeAttribute("aria-busy");
      S.last = { screen, data };
      draw();
    } catch (err) {
      if (my !== S.req) return;
      if (err.kind === "validation" && err.field) {
        const input = form.querySelector(`[name="${err.field}"]`);
        input?.classList.add("invalid");
        errBox.textContent = `${err.message} ${err.hint}`;
        errBox.hidden = false;
      }
      States.error(main, err, load);
    }
  }

  function draw() {
    if (!S.last) return;
    S.last.screen.render(main, S.last.data, { filters: S.filters, setExtra: (x) => { Object.assign(S.extra, x); load(); } });
  }
  // Vẽ lại biểu đồ khi đổi kích thước cửa sổ (biểu đồ vẽ theo bề rộng thật của khung)
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (!main.hasAttribute("aria-busy") && main.querySelector(".chart")) draw(); }, 200); });

  /* -------- khởi động: đọc meta (danh mục cửa hàng, khoảng ngày) -------- */
  async function init() {
    States.loading(main, { text: "Đang kết nối kho dữ liệu…" });
    try {
      S.meta = await Api.meta();
    } catch (err) {
      badge.textContent = "Không kết nối được kho dữ liệu";
      badge.classList.add("bad");
      States.error(main, err, init);
      return;
    }
    badge.classList.remove("bad");
    const m = S.meta;
    badge.textContent = m.has_data
      ? `Dữ liệu ${Fmt.date(m.min_date)} – ${Fmt.date(m.max_date)} · nạp lúc ${Fmt.dateTime(m.source.updated_at)}`
      : "Kho chưa có dữ liệu";
    form.store.innerHTML = `<option value="">Tất cả</option>` +
      m.stores.map((s) => `<option value="${s.store_code}">${s.store_code} · ${Fmt.esc(s.store_name.replace("Mekong Mobile ", ""))}</option>`).join("");
    form.category.innerHTML = `<option value="">Tất cả</option>` +
      m.categories.map((c) => `<option>${Fmt.esc(c)}</option>`).join("");
    S.filters = { from: m.default_filter.from, to: m.default_filter.to, store: "", category: "" };
    writeForm(S.filters);
    if (!m.has_data) { States.empty(main, "empty_warehouse"); return; }
    load();
  }

  /* -------- sự kiện -------- */
  form.addEventListener("submit", (e) => { e.preventDefault(); S.filters = readForm(); load(); });
  form.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
    if (!S.meta?.max_date) return;
    Object.assign(S.filters, readForm(), presetRange(b.dataset.preset));
    writeForm(S.filters);
    load();
  }));
  document.getElementById("export-btn").addEventListener("click", (e) => {
    e.currentTarget.href = Api.exportUrl(readForm());     // FR-07: xuất theo đúng bộ lọc đang chọn
  });
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => { x.classList.toggle("active", x === t); x.setAttribute("aria-selected", x === t); });
    S.screen = t.dataset.screen;
    if (S.meta) load(); else init();
  }));

  init();
})();
