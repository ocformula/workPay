"""REST API wrappers for the React SPA frontend."""
import json
from flask import jsonify, request, session, redirect, url_for

from db import (
    get_employees,
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
)
from config import ADMIN_PASSWORD


def register_api(app):
    """Register /api/* routes returning JSON."""

    @app.route("/api/employees")
    def api_employees():
        return jsonify(get_employee_overview())

    @app.route("/api/employees/<employee_name>")
    def api_employee_calculations(employee_name):
        rows = get_employee_calculations(employee_name)
        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "week_start_date": row["week_start_date"],
                "week_end_date": row["week_end_date"],
                "normal_start": row["normal_start"],
                "normal_end": row["normal_end"],
                "created_at": row["created_at"],
                "week_total_min": json.loads(row["result_json"]).get("week_total_min", 0),
                "bucket_15_total": json.loads(row["result_json"]).get("bucket_15_total", 0),
                "bucket_20_total": json.loads(row["result_json"]).get("bucket_20_total", 0),
                "bucket_25_total": json.loads(row["result_json"]).get("bucket_25_total", 0),
                "needs_review": bool(row["needs_review"]) if "needs_review" in row.keys() else False,
                "auto_carryover": bool(json.loads(row["input_json"]).get("auto_carryover")),
                "carryover_from": json.loads(row["input_json"]).get("carryover_from"),
            })
        return jsonify(items)

    @app.route("/api/calculator/result", methods=["POST"])
    def api_calculator_result():
        """Receive calculation input, compute and return result JSON."""
        data = request.get_json()
        # Delegate to existing logic — for now return placeholder
        # Full implementation mirrors routes_calculator.py's /calculator/result
        return jsonify({"status": "ok"})

    @app.route("/api/calculator/save", methods=["POST"])
    def api_calculator_save():
        data = request.get_json()
        input_json = json.dumps(data, ensure_ascii=False)
        result_json = json.dumps({}, ensure_ascii=False)  # computed elsewhere
        save_weekly_calculation(
            employee_name=data["employee_name"],
            week_start_date=data["week_start_date"],
            week_end_date="",
            normal_start=data["normal_start"],
            normal_end=data["normal_end"],
            input_json=input_json,
            result_json=result_json,
        )
        return jsonify({"status": "saved"})

    @app.route("/api/admin/login", methods=["POST"])
    def api_admin_login():
        pw = request.get_json().get("password", "")
        if pw == ADMIN_PASSWORD:
            session["admin_ok"] = True
            return jsonify({"status": "ok"})
        from flask import abort
        abort(401)

    @app.route("/api/admin/logout", methods=["POST"])
    def api_admin_logout():
        session.pop("admin_ok", None)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/employees")
    def api_admin_employees():
        if not session.get("admin_ok"):
            from flask import abort
            abort(401)
        return jsonify(get_employee_admin_list())

    @app.route("/api/admin/employees/add", methods=["POST"])
    def api_admin_add_employee():
        if not session.get("admin_ok"):
            from flask import abort
            abort(401)
        name = request.get_json().get("employee_name", "").strip()
        if name:
            add_employee(name)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/employees/<int:employee_id>/delete", methods=["POST"])
    def api_admin_delete_employee(employee_id):
        if not session.get("admin_ok"):
            from flask import abort
            abort(401)
        pw = request.get_json().get("password", "")
        if pw != ADMIN_PASSWORD:
            from flask import abort
            abort(401)
        calc_count, trash_count = get_employee_usage_counts(employee_id)
        if calc_count > 0 or trash_count > 0:
            from flask import abort
            abort(400, description="Employee has calculations")
        delete_employee_by_id(employee_id)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/trash")
    def api_admin_trash():
        if not session.get("admin_ok"):
            from flask import abort
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
            from flask import abort
            abort(401)
        restore_deleted_calculation(trash_id)
        return jsonify({"status": "ok"})

    @app.route("/api/admin/trash/<int:trash_id>/purge", methods=["POST"])
    def api_purge_trash(trash_id):
        if not session.get("admin_ok"):
            from flask import abort
            abort(401)
        purge_deleted_calculation(trash_id)
        return jsonify({"status": "ok"})
