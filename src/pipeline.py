"""ĐIỂM CHẠY DUY NHẤT của pipeline ETL — luồng L6.

    python -m src.pipeline                 # dùng DATA_DIR trong .env (mặc định data/sample)
    python -m src.pipeline --data-dir data/raw

Ba pha nằm ở ba thư mục riêng: src/extract → src/transform (+ src/quality) → src/load.
Tệp này chỉ điều phối, ghi nhật ký lần chạy và báo cáo chất lượng; không chứa quy tắc nghiệp vụ.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

from src.config import get_settings
from src.extract.extract import ExtractError, extract_all
from src.load import warehouse
from src.transform.transform import TransformResult, transform


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_quality_report(report_dir: Path, run: dict, result: TransformResult) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    reject_by_rule = (result.rejects.groupby("rule_code").size().to_dict()
                      if not result.rejects.empty else {})
    payload = {
        "run": run,
        "stats": result.stats,
        "checks": [c.summary() for c in result.checks],
        "rejects_by_rule": reject_by_rule,
        "fixes": len(result.fixes),
    }
    path = report_dir / f"quality_report_{run['run_id']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (report_dir / "quality_report_latest.json").write_text(path.read_text(encoding="utf-8"),
                                                           encoding="utf-8")
    return path


def run_pipeline(data_dir: Path | None = None, dw_path: Path | None = None,
                 report_dir: Path | None = None, today: date | None = None,
                 verbose: bool = True, reference_dir: Path | None = None) -> dict:
    """Chạy E → T → L. Trả về dict tóm tắt lần chạy (dùng cho test và in ra màn hình)."""
    s = get_settings()
    data_dir = data_dir or s.data_dir
    dw_path = dw_path or s.dw_path
    report_dir = report_dir or s.report_dir
    reference_dir = reference_dir or s.reference_dir
    run = {"run_id": f"RUN-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}",
           "started_at": _now(), "source_dir": str(data_dir), "status": "RUNNING"}
    log = print if verbose else (lambda *a, **k: None)

    conn = warehouse.connect(dw_path)
    try:
        warehouse.init_schema(conn)
        log(f"[{run['run_id']}] EXTRACT  từ {data_dir}")
        ex = extract_all(data_dir, reference_dir)
        for name, n in ex.row_counts.items():
            log(f"    {name:<24} {n:>7} dòng")

        log("[TRANSFORM] áp 10 quy tắc chất lượng CL01–CL10")
        res = transform(ex.frames, s.quality_threshold, today)
        for c in res.checks:
            flag = "ĐẠT " if c.passed else "VƯỢT"
            log(f"    {c.rule_code} {c.rule_name:<44} lỗi {c.rows_failed:>5}/{c.rows_checked:<6}"
                f" = {c.fail_rate:>6.3f}%  (ngưỡng ≤{c.max_fail_rate}%) {flag} [{c.action}]")

        log(f"[LOAD] nạp vào {dw_path}")
        fact_after = warehouse.load(conn, res, run["run_id"], _now())

        run.update(status="SUCCESS", finished_at=_now(),
                   rows_extracted=res.stats["rows_extracted"], rows_loaded=res.stats["rows_loaded"],
                   rows_rejected=res.stats["rows_rejected"], rows_fixed=res.stats["rows_fixed"],
                   valid_rate=res.stats["valid_rate"], fact_rows_after=fact_after)
        warehouse.write_run_log(conn, run)
        report = write_quality_report(report_dir, run, res)

        log("-" * 72)
        log(f"Dòng trích xuất : {run['rows_extracted']:>7}   (đơn {res.stats['orders_extracted']}"
            f" + dòng hàng {res.stats['items_extracted']})")
        log(f"Dòng đã nạp     : {run['rows_loaded']:>7}")
        log(f"Dòng bị loại    : {run['rows_rejected']:>7}   (chi tiết: bảng reject_records)")
        log(f"Dòng được sửa   : {run['rows_fixed']:>7}   (chi tiết: bảng fix_log)")
        verdict = "ĐẠT" if res.stats["valid_rate_passed"] else "KHÔNG ĐẠT"
        log(f"Tỉ lệ hợp lệ    : {run['valid_rate']:>6}%  (ngưỡng ≥ {s.quality_threshold}%) → {verdict}")
        log(f"Tổng dòng fact_order_item sau khi nạp: {fact_after}")
        log(f"Báo cáo chất lượng: {report}")
        return run
    except ExtractError as exc:
        run.update(status="FAILED", finished_at=_now(), error_message=str(exc))
        warehouse.write_run_log(conn, run)
        log(f"[LỖI NGUỒN] {exc}")
        raise
    except Exception as exc:  # lỗi không lường trước: ghi log, giữ nguyên kho (đã ROLLBACK)
        run.update(status="FAILED", finished_at=_now(),
                   error_message=f"{type(exc).__name__}: {exc}")
        warehouse.write_run_log(conn, run)
        log(f"[LỖI] Pipeline dừng, kho dữ liệu giữ nguyên trạng thái trước lần chạy. {exc}")
        raise
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pipeline ETL kho dữ liệu bán hàng Mekong Mobile (L6)")
    ap.add_argument("--data-dir", type=Path, help="Thư mục chứa tệp nguồn (ghi đè DATA_DIR)")
    args = ap.parse_args(argv)
    try:
        run_pipeline(data_dir=args.data_dir)
        return 0
    except ExtractError:
        return 2
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
