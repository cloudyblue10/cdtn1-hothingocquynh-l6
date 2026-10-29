"""Lỗi nghiệp vụ dùng chung cho lớp service và routes.

Mỗi lỗi mang đủ 3 phần cho người dùng: chuyện gì (message) · vì sao/làm gì tiếp (hint)
và một mã (code) để tra cứu. Lớp service chỉ NÉM lỗi; việc đổi thành mã HTTP do routes làm.
"""
from __future__ import annotations


class AppError(Exception):
    code = "APP_ERROR"
    http_status = 500

    def __init__(self, message: str, hint: str = "", field: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.field = field

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message, "hint": self.hint}
        if self.field:
            d["field"] = self.field
        return d


class ValidationError(AppError):
    """Tham số bộ lọc không hợp lệ (ngày sai định dạng, từ ngày > đến ngày, ...)."""
    code = "INVALID_FILTER"
    http_status = 400


class WarehouseUnavailable(AppError):
    """Không mở được kho dữ liệu (chưa chạy pipeline, tệp bị xoá/khoá, lỗi đọc)."""
    code = "DW_UNAVAILABLE"
    http_status = 503
