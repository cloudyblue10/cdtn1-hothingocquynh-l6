/* Thư viện biểu đồ SVG tự viết (không phụ thuộc CDN => chạy được offline khi chấm bài).
 * Mỗi biểu đồ có: một trục duy nhất, đường tham chiếu nét đứt (trung bình / ngưỡng),
 * tooltip khi rê chuột, và nhãn chữ dùng màu chữ (không dùng màu chuỗi). */
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }

  /** Bề rộng thật của khung (px) => chữ luôn đúng 11px, không bị co/giãn theo viewBox. */
  const widthOf = (el) => Math.max(300, Math.floor(el.clientWidth || el.parentElement.clientWidth || 760));

  function mount(el, w, h) {
    el.innerHTML = "";
    el.classList.add("chart");
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("role", "img");
    const tip = document.createElement("div");
    tip.className = "tooltip";
    el.append(svg, tip);
    return { svg, tip };
  }

  function add(parent, tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (text !== undefined) n.textContent = text;
    parent.appendChild(n);
    return n;
  }

  function showTip(el, svg, tip, html, sx, sy) {
    const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
    const host = el.getBoundingClientRect();
    tip.innerHTML = html;
    tip.style.left = (r.left - host.left + (sx / vb.width) * r.width) + "px";
    tip.style.top = (r.top - host.top + (sy / vb.height) * r.height) + "px";
    tip.classList.add("show");
  }
  const hideTip = (tip) => tip.classList.remove("show");

  /** Thanh có đầu dữ liệu bo tròn 4px, gốc vuông bám đường nền. */
  function barPath(x, y, w, h, horizontal) {
    const r = Math.min(4, (horizontal ? h : w) / 2, horizontal ? w : h);
    if (horizontal) return `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`;
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  }

  /* ---------------- Biểu đồ đường theo thời gian ---------------- */
  function line(el, { points, refValue = null, refLabel = "", highlights = [], yFmt = Fmt.vnd, tipFmt, ariaLabel = "" }) {
    const W = widthOf(el), H = 280, m = { l: 64, r: 18, t: 16, b: 30 };
    const { svg, tip } = mount(el, W, H);
    svg.setAttribute("aria-label", ariaLabel);
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const maxY = niceMax(Math.max(...points.map((p) => p.y), refValue || 0));
    const x = (i) => m.l + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw);
    const y = (v) => m.t + ih - (v / maxY) * ih;

    const g = add(svg, "g", { class: "axis" });
    for (let k = 0; k <= 4; k++) {
      const v = (maxY / 4) * k;
      add(g, "line", { class: k === 0 ? "baseline" : "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) });
      add(g, "text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, yFmt(v));
    }
    const step = Math.max(1, Math.ceil(points.length / 8));
    points.forEach((p, i) => {
      if (i % step === 0 || i === points.length - 1) add(g, "text", { x: x(i), y: H - 8, "text-anchor": "middle" }, p.label);
    });

    const d = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.y)}`).join(" ");
    add(svg, "path", { class: "area", d: `${d} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z` });
    add(svg, "path", { class: "line", d });
    if (refValue !== null) {
      add(svg, "line", { class: "refline", x1: m.l, x2: W - m.r, y1: y(refValue), y2: y(refValue) });
      add(svg, "text", { class: "reflabel", x: W - m.r, y: y(refValue) - 6, "text-anchor": "end" }, refLabel);
    }
    const hs = new Set(highlights);
    points.forEach((p, i) => { if (hs.has(p.key)) add(svg, "circle", { class: "alert-dot", cx: x(i), cy: y(p.y), r: 5 }); });

    const cross = add(svg, "line", { class: "crosshair", y1: m.t, y2: m.t + ih, x1: 0, x2: 0, visibility: "hidden" });
    const dot = add(svg, "circle", { class: "dot", r: 5, cx: 0, cy: 0, visibility: "hidden" });
    const hit = add(svg, "rect", { class: "hit", x: m.l, y: m.t, width: iw, height: ih });
    hit.addEventListener("mousemove", (ev) => {
      const r = svg.getBoundingClientRect();
      const sx = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(points.length - 1, Math.round(((sx - m.l) / iw) * (points.length - 1))));
      const p = points[i];
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible"); dot.setAttribute("visibility", "visible");
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(p.y));
      showTip(el, svg, tip, tipFmt ? tipFmt(p) : `${p.label}<br>${yFmt(p.y)}`, x(i), y(p.y));
    });
    hit.addEventListener("mouseleave", () => { hideTip(tip); cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
  }

  /* ---------------- Biểu đồ thanh ngang (xếp hạng) ---------------- */
  function hbar(el, { items, refValue = null, refLabel = "", valueFmt = Fmt.vnd, tipFmt, labelWidth = 170, ariaLabel = "" }) {
    const rowH = 24, gap = 2, W = widthOf(el), m = { l: labelWidth, r: 70, t: refValue !== null ? 22 : 6, b: 8 };
    const H = m.t + m.b + items.length * (rowH + gap);
    const { svg, tip } = mount(el, W, H);
    svg.setAttribute("aria-label", ariaLabel);
    const iw = W - m.l - m.r;
    const maxV = niceMax(Math.max(...items.map((i) => i.value), refValue || 0));
    const sx = (v) => (v / maxV) * iw;
    add(svg, "line", { class: "baseline", x1: m.l, x2: m.l, y1: m.t - 4, y2: H - m.b });
    items.forEach((it, i) => {
      const yy = m.t + i * (rowH + gap);
      const label = it.label.length > 26 ? it.label.slice(0, 25) + "…" : it.label;
      add(svg, "text", { class: "lbl", x: m.l - 8, y: yy + rowH / 2 + 4, "text-anchor": "end" }, label);
      const bar = add(svg, "path", { class: "bar" + (it.highlight ? " hi" : ""), d: barPath(m.l, yy + 3, Math.max(sx(it.value), 1), rowH - 6, true) });
      add(svg, "text", { class: "valtext", x: m.l + sx(it.value) + 6, y: yy + rowH / 2 + 4 }, valueFmt(it.value));
      const hit = add(svg, "rect", { class: "hit", x: 0, y: yy, width: W, height: rowH });
      hit.addEventListener("mousemove", () => { bar.style.opacity = .8; showTip(el, svg, tip, tipFmt ? tipFmt(it) : `${Fmt.esc(it.label)}<br>${valueFmt(it.value)}`, m.l + sx(it.value) / 2, yy); });
      hit.addEventListener("mouseleave", () => { bar.style.opacity = 1; hideTip(tip); });
    });
    if (refValue !== null) {
      add(svg, "line", { class: "refline", x1: m.l + sx(refValue), x2: m.l + sx(refValue), y1: m.t - 6, y2: H - m.b });
      add(svg, "text", { class: "reflabel", x: m.l + sx(refValue), y: 12, "text-anchor": "middle" }, refLabel);
    }
  }

  /* ---------------- Biểu đồ cột theo tháng ---------------- */
  function columns(el, { items, refValue = null, refLabel = "", yFmt = Fmt.vnd, tipFmt, ariaLabel = "" }) {
    const W = widthOf(el), H = 260, m = { l: 56, r: 16, t: 18, b: 30 };
    const { svg, tip } = mount(el, W, H);
    svg.setAttribute("aria-label", ariaLabel);
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const maxY = niceMax(Math.max(...items.map((i) => i.value), refValue || 0));
    const y = (v) => m.t + ih - (v / maxY) * ih;
    const g = add(svg, "g", { class: "axis" });
    for (let k = 0; k <= 4; k++) {
      const v = (maxY / 4) * k;
      add(g, "line", { class: k === 0 ? "baseline" : "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) });
      add(g, "text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, yFmt(v));
    }
    const slot = iw / items.length, bw = Math.max(4, Math.min(34, slot - 2));
    const step = Math.max(1, Math.ceil(items.length / 10));
    items.forEach((it, i) => {
      const cx = m.l + slot * i + slot / 2;
      const bar = add(svg, "path", { class: "bar" + (it.highlight ? " hi" : ""), d: barPath(cx - bw / 2, y(it.value), bw, Math.max(y(0) - y(it.value), 1), false) });
      if (i % step === 0 || i === items.length - 1) add(g, "text", { x: cx, y: H - 8, "text-anchor": "middle" }, it.label);
      const hit = add(svg, "rect", { class: "hit", x: cx - slot / 2, y: m.t, width: slot, height: ih });
      hit.addEventListener("mousemove", () => { bar.style.opacity = .8; showTip(el, svg, tip, tipFmt ? tipFmt(it) : `${it.label}<br>${yFmt(it.value)}`, cx, y(it.value)); });
      hit.addEventListener("mouseleave", () => { bar.style.opacity = 1; hideTip(tip); });
    });
    if (refValue !== null) {
      add(svg, "line", { class: "refline", x1: m.l, x2: W - m.r, y1: y(refValue), y2: y(refValue) });
      add(svg, "text", { class: "reflabel", x: W - m.r, y: y(refValue) - 6, "text-anchor": "end" }, refLabel);
    }
  }

  return { line, hbar, columns };
})();
