"""LỚP ROUTES (HTTP) — Flask. Chỉ làm 3 việc:
  1. lấy tham số từ request,
  2. gọi DashboardService,
  3. đổi kết quả/lỗi thành JSON + mã HTTP.
Không có SQL, không có công thức nghiệp vụ ở đây.

Chạy:  python -m src.serve.app        → mở http://127.0.0.1:8000
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from src.config import get_settings
from src.serve.errors import AppError
from src.serve.repository import WarehouseRepository
from src.serve.service import DashboardService

STATIC_DIR = Path(__file__).resolve().parent / "static"
log = logging.getLogger("dashboard")


def create_app(service: DashboardService | None = None) -> Flask:
    """Application factory — test truyền service dùng kho tạm, không cần máy chủ thật."""
    s = get_settings()
    service = service or DashboardService(WarehouseRepository(s.dw_path), s.alert_threshold,
                                          s.quality_threshold)
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.json.ensure_ascii = False

    # ---------------------------------------------------------- xử lý lỗi tập trung
    @app.errorhandler(AppError)
    def _app_error(err: AppError):
        return jsonify({"error": err.to_dict()}), err.http_status

    @app.errorhandler(404)
    def _not_found(_):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Không có đường dẫn này.",
                                  "hint": "Kiểm tra lại địa chỉ API."}}), 404

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        ref = uuid.uuid4().hex[:6].upper()
        log.exception("Lỗi không lường trước [%s]: %s", ref, err)   # chi tiết chỉ nằm trong log
        return jsonify({"error": {"code": "INTERNAL", "ref": ref,
                                  "message": "Hệ thống gặp sự cố khi xử lý yêu cầu.",
                                  "hint": f"Vui lòng thử lại sau ít phút. Mã tra cứu: {ref}."}}), 500

    # ---------------------------------------------------------- trang
    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    # ---------------------------------------------------------- API
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/meta")
    def meta():
        return jsonify(service.meta())

    @app.get("/api/overview")
    def overview():
        return jsonify(service.overview(request.args.to_dict()))

    @app.get("/api/products")
    def products():
        return jsonify(service.products(request.args.to_dict()))

    @app.get("/api/stores")
    def stores():
        return jsonify(service.stores(request.args.to_dict()))

    @app.get("/api/payments")
    def payments():
        return jsonify(service.payments(request.args.to_dict()))

    @app.get("/api/quality")
    def quality():
        return jsonify(service.quality(request.args.to_dict()))

    @app.get("/api/export.csv")
    def export_csv():
        name, content = service.export_csv(request.args.to_dict())
        return Response(content, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = get_settings()
    print(f"Dashboard: http://{cfg.api_host}:{cfg.api_port}  (kho: {cfg.dw_path})")
    create_app().run(host=cfg.api_host, port=cfg.api_port, debug=False)
