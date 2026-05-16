"""REST API wrappers for the React SPA frontend."""
import json
import csv
import io
from datetime import date, datetime, time, timedelta
from flask import jsonify, request, session, abort, make_response

from db import (
    get_employee_overview,
    get_employee_calculations,
    get_employee_admin_list,
    add_employee,
    delete_employee_by_id,
    get_employee_usage_counts,
    get_deleted_calculations,
    restore_deleted_calculation,
    purge_deleted_calculation,
    save_weekly_calculation,
    get_calculation_by_id,
    move_calculation_to_trash,
)
from calc_weekly import WeekWork, DayWork, WorkSegment, calculate_week_work
from config import ADMIN_PASSWORD


def register_api(app):
    """Register /api/* routes returning JSON."""

    # --------------- Employees ---------------

    @app.route("/api/employees")
    def api_employees():
        return jsonify(get_employee_overview())

    @app.route("/api/employees/<employee_name>")
    def api_employee_calculations(employee_name):
        rows = get_employee_calculations(employee_name)
        items = []
        for row in rows:
            result = json.loads(row["result_json"])
            inp = json.loads(row["input_json"])
            items.append({
                "id": row["id"],
                "week_start_date": row["week_start_date"],
                "week_end_date": row["week_end_date"],
                "normal_start": row["normal_start"],
                "normal_end": row["normal_end"],
                "created_at": row["created_at"],
                "week_total_min": result.get("week_total_min", 0),
                "bucket_15_total": result.get("bucket_15_total", 0),
                "bucket_20_total": result.get("bucket_20_total", 0),
                "bucket_25_total": result.get("bucket_25_total", 0),
                "needs_review": bool(row["needs_review"]) if "needs_review" in row.keys() else False,
                "auto_carryover": bool(inp.get("auto_carryover")),
                "carryover_from": inp.get("carryover_from"),
                "input_json": inp,
                "result_json": result,
            })
        return jsonify(items)

    @app.route("/api/employees/<employee_name>/<int:calc_id>")
    def api_calculation_detail(employee_name, calc_id):
        row = get_calculation_by_id(calc_id)
        if not row or row["employee_name"] != employee_name:
            abort(404)
        result = json.loads(row["result_json"])
        inp = json.loads(row["input_json"])
        return jsonify({
            "id": row["id"],
            "week_start_date": row["week_start_date"],
            "week_end_date": row["week_end_date"],
            "normal_start": row["normal_start"],
            "normal_end": row["normal_end"],
            "created_at": row["created_at"],
            "input": inp,
            "result": result,
        })

    @app.route("/api/employees/<employee_name>/<int:calc_id>/delete", methods=["POST"])
    def api_delete_calculation(employee_name, calc_id):
        row = get_calculation_by_id(calc_id)
        if not row or row["employee_name"] != employee_name:
            abort(404)
        move_calculation_to_trash(calc_id)
        return jsonify({"status": "deleted"})

    # --------------- Calculator ---------------

    @app.route("/api/calculator/result", methods=["POST"])
    def api_calculator_result():
        """Compute weekly work from JSON input, return result."""
        data = request.get_json()
        employee_name = data.get("employee_name", "")
        week_start_str = data.get("week_start_date", "")
        normal_start = data.get("normal_start", "09:00")
        normal_end = data.get("normal_end", "18:00")
        days_data = data.get("days", [])

        week_start_date = date.fromisoformat(week_start_str)

        days = []
        for day_data in days_data:
            current_date = date.fromisoformat(day_data["date"])
            is_holiday = bool(day_data.get("is_holiday"))
            is_off = bool(day_data.get("is_off"))

            if is_off:
                days.append(DayWork(current_date, [], is_holiday=is_holiday))
                continue

            segments = []
            for seg in day_data.get("segments", []):
                try:
                    segments.append(WorkSegment(seg["start"], seg["end"], is_holiday=False))
                except (ValueError, KeyError):
                    abort(400, description=f"Invalid time format for {current_date}")

            day_work = DayWork(current_date, segments, is_holiday=is_holiday)
            day_work.memo = day_data.get("memo", "")
            days.append(day_work)

        week_work = WeekWork(week_start_date, days)
        result = calculate_week_work(week_work, normal_start, normal_end)
        result["_input"] = data
        return jsonify(result)

    @app.route("/api/calculator/save", methods=["POST"])
    def api_calculator_save():
        """Compute and save a weekly calculation."""
        data = request.get_json()
        employee_name = data.get("employee_name", "")
        week_start_str = data.get("week_start_date", "")
        normal_start = data.get("normal_start", "09:00")
        normal_end = data.get("normal_end", "18:00")
        days_data = data.get("days", [])

        week_start_date = date.fromisoformat(week_start_str)
        week_end_date = week_start_date + timedelta(days=6)

        days = []
        for day_data in days_data:
            current_date = date.fromisoformat(day_data["date"])
            is_holiday = bool(day_data.get("is_holiday"))
            is_off = bool(day_data.get("is_off"))

            if is_off:
                days.append(DayWork(current_date, [], is_holiday=is_holiday))
                continue

            segments = []
            for seg in day_data.get("segments", []):
                try:
                    segments.append(WorkSegment(seg["start"], seg["end"], is_holiday=False))
                except (ValueError, KeyError):
                    abort(400, description=f"Invalid time format for {current_date}")

            day_work = DayWork(current_date, segments, is_holiday=is_holiday)
            day_work.memo = day_data.get("memo", "")
            days.append(day_work)

        week_work = WeekWork(week_start_date, days)
        result = calculate_week_work(week_work, normal_start, normal_end)
        needs_review = result.get("needs_review", False)

        input_json = json.dumps(data, ensure_ascii=False)
        result_clean = {k: v for k, v in result.items() if not k.startswith("_")}
        result_json = json.dumps(result_clean, ensure_ascii=False, default=str)

        save_weekly_calculation(
            employee_name=employee_name,
            week_start_date=week_start_date.isoformat(),
            week_end_date=week_end_date.isoformat(),
            normal_start=normal_start,
            normal_end=normal_end,
            input_json=input_json,
            result_json=result_json,
            needs_review=needs_review,
        )

        return jsonify({"status": "saved", "result": result_clean})

    @app.route("/api/calculator/export", methods=["POST"])
    def api_calculator_export():
        """Export calculation result to Excel."""
        from openpyxl import Workbook

        data = request.get_json()
        result = data.get("result", {})
        input_data = data.get("input", {})

        wb = Workbook()
        ws = wb.active
        ws.title = "계산결과"

        # Header
        ws.append([input_data.get("employee_name", ""), "주간 근무 계산 결과"])
        ws.append([f"주차: {input_data.get('week_start_date', '')} ~ {data.get('week_end_date', '')}"])
        ws.append([])

        # Day results
        ws.append(["요일", "일자", "근로(분)", "휴게(분)", "연장(분)", "1.5배", "2.0배", "2.5배"])
        for day in result.get("day_results", []):
            ws.append([
                day.get("weekday", ""),
                day.get("date", ""),
                day.get("work_min", 0),
                day.get("break_min", 0),
                day.get("overtime_min", 0),
                day.get("bucket_15_min", 0),
                day.get("bucket_20_min", 0),
                day.get("bucket_25_min", 0),
            ])

        ws.append([])
        ws.append(["총계", "", result.get("week_total_min", 0), "", "",
                    result.get("bucket_15_total", 0), result.get("bucket_20_total", 0),
                    result.get("bucket_25_total", 0)])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        resp = make_response(output.getvalue())
        resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"workpay_{input_data.get('employee_name', '')}_{input_data.get('week_start_date', '')}.xlsx"
        resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
        return resp

    # --------------- Admin ---------------

    @app.route("/api/admin/login", methods=["POST"])
    def api_admin_login():
        pw = request.get_json().get("password", "")
        if pw == ADMIN_PASSWORD:
            session["admin_ok"] = True
            return jsonify({"status": "ok"})
        abort(401)

    @app.route("/api/admin/logout", methods=["POST"])
    def api_admin_logout():
        session.pop("admin_ok", None)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/employees")
    def api_admin_employees():
        if not session.get("admin_ok"):
            abort(401)
        return jsonify(get_employee_admin_list())

    @app.route("/api/admin/employees/add", methods=["POST"])
    def api_admin_add_employee():
        if not session.get("admin_ok"):
            abort(401)
        name = request.get_json().get("employee_name", "").strip()
        if name:
            add_employee(name)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/employees/<int:employee_id>/delete", methods=["POST"])
    def api_admin_delete_employee(employee_id):
        if not session.get("admin_ok"):
            abort(401)
        pw = request.get_json().get("password", "")
        if pw != ADMIN_PASSWORD:
            abort(401)
        calc_count, trash_count = get_employee_usage_counts(employee_id)
        if calc_count > 0 or trash_count > 0:
            abort(400, description="Employee has calculations")
        delete_employee_by_id(employee_id)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/trash")
    def api_admin_trash():
        if not session.get("admin_ok"):
            abort(401)
        rows = get_deleted_calculations()
        return jsonify([{
            "id": r["id"],
            "employee_name": r["employee_name"],
            "week_start_date": r["week_start_date"],
            "week_end_date": r["week_end_date"],
            "deleted_at": r["deleted_at"],
        } for r in rows])

    @app.route("/api/admin/trash/<int:trash_id>/restore", methods=["POST"])
    def api_restore_trash(trash_id):
        if not session.get("admin_ok"):
            abort(401)
        restore_deleted_calculation(trash_id)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/trash/<int:trash_id>/purge", methods=["POST"])
    def api_purge_trash(trash_id):
        if not session.get("admin_ok"):
            abort(401)
        purge_deleted_calculation(trash_id)
        return jsonify({"status": "ok"})
