/* LỚP CLIENT API — nơi DUY NHẤT trong giao diện gọi fetch().
 * Màn hình không biết URL hay mã HTTP; chỉ nhận dữ liệu hoặc một ApiError đã chuẩn hoá. */
class ApiError extends Error {
  constructor({ kind, status = 0, code = "", message, hint = "", field = null, ref = null }) {
    super(message);
    Object.assign(this, { kind, status, code, hint, field, ref });
  }
}

const Api = (() => {
  const BASE = "/api";
  const TIMEOUT_MS = 10000;

  function qs(params) {
    const p = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== "") p.set(k, v); });
    const s = p.toString();
    return s ? "?" + s : "";
  }

  async function get(path, params) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    let res;
    try {
      res = await fetch(BASE + path + qs(params), { signal: ctrl.signal, headers: { Accept: "application/json" } });
    } catch (e) {
      // Máy chủ tắt / mất mạng / quá thời gian chờ — KHÔNG đưa chuỗi lỗi kỹ thuật ra màn hình
      throw new ApiError({
        kind: "network",
        message: e.name === "AbortError"
          ? "Máy chủ dashboard không phản hồi sau 10 giây."
          : "Không kết nối được tới máy chủ dashboard.",
        hint: "Kiểm tra máy chủ đang chạy (python -m src.serve.app) và mạng, rồi bấm Thử lại.",
      });
    } finally {
      clearTimeout(timer);
    }
    let body = null;
    try { body = await res.json(); } catch (_) { /* phản hồi không phải JSON */ }
    if (!res.ok) {
      const e = (body && body.error) || {};
      throw new ApiError({
        kind: res.status === 400 ? "validation" : res.status === 503 ? "warehouse" : "server",
        status: res.status, code: e.code, field: e.field, ref: e.ref,
        message: e.message || `Máy chủ trả lỗi ${res.status}.`,
        hint: e.hint || "Vui lòng thử lại sau ít phút.",
      });
    }
    return body;
  }

  return {
    meta: () => get("/meta"),
    overview: (f) => get("/overview", f),
    products: (f) => get("/products", f),
    stores: (f) => get("/stores", f),
    payments: (f) => get("/payments", f),
    quality: (f) => get("/quality", f),
    exportUrl: (f) => BASE + "/export.csv" + qs(f),
  };
})();
