/* Định dạng số liệu tiếng Việt — dùng chung cho mọi màn hình. */
const Fmt = (() => {
  const nf0 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });

  /** 414205989000 -> "414,2 tỷ"; 356956000 -> "357,0 tr" */
  function vnd(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e9) return nf1.format(v / 1e9) + " tỷ";
    if (a >= 1e6) return nf1.format(v / 1e6) + " tr";
    return nf0.format(v) + " đ";
  }
  const vndFull = (v) => (v === null || v === undefined ? "—" : nf0.format(v) + " đ");
  const int = (v) => (v === null || v === undefined ? "—" : nf0.format(v));
  const pct = (v, d = 1) => (v === null || v === undefined ? "—" : (d === 2 ? nf2 : nf1).format(v) + "%");
  const date = (iso) => { if (!iso) return "—"; const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}/${m}/${y}`; };
  const dateTime = (iso) => (iso ? date(iso) + " " + iso.slice(11, 16) : "—");

  /** Mũi tên + % so với kỳ trước; null => "không có kỳ trước để so". */
  function delta(v, unit = "%") {
    if (v === null || v === undefined) return `<span class="delta flat">— (kỳ trước = 0)</span>`;
    const cls = v > 0 ? "up" : v < 0 ? "down" : "flat";
    const arrow = v > 0 ? "▲" : v < 0 ? "▼" : "■";
    return `<span class="delta ${cls}">${arrow} ${nf1.format(Math.abs(v))}${unit}</span>`;
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  return { vnd, vndFull, int, pct, date, dateTime, delta, esc };
})();
