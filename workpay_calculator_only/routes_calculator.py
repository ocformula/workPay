from datetime import date, datetime, time, timedelta
import json
import csv
import io

from flask import render_template, request, redirect, url_for, flash, make_response, session

from calc_weekly import WeekWork, DayWork, WorkSegment, calculate_week_work
from config import DAY_LIMIT_MIN, WEEK_LIMIT_40_MIN, ADMIN_PASSWORD
from typing import Optional, Tuple
from db import (
    init_db,
    get_employees,
    get_employee_overview,
    get_employee_calculations,
    get_employee_id,
    add_employee,
    get_employee_admin_list,
    get_employee_usage_counts,
    delete_employee_by_id,
    get_calculation_by_id,
    delete_calculation_by_id,
    move_calculation_to_trash,
    get_deleted_calculations,
    get_deleted_calculation_by_id,
    restore_deleted_calculation,
    purge_deleted_calculation,
    save_weekly_calculation,
    get_worklogs,
    get_worklog_by_id,
    add_worklog,
    update_worklog,
    delete_worklog,
)
from time_utils import week_start


def register(app):
    init_db()

    def _format_break_label(label: str) -> str:
        if not label:
            return label
        cleaned = label.replace("[휴일] ", "").strip()
        if "~" in cleaned:
            left, right = cleaned.split("~", 1)
            left = left.strip()
            right = right.strip()
            if " " in left and "/" in left.split(" ", 1)[0]:
                left = left.split(" ", 1)[1]
            if " " in right and "/" in right.split(" ", 1)[0]:
                right = right.split(" ", 1)[1]
            return f"{left}~{right}"
        if " " in cleaned and "/" in cleaned.split(" ", 1)[0]:
            return cleaned.split(" ", 1)[1]
        return cleaned

    def _admin_allowed() -> bool:
        return bool(session.get("admin_ok"))

    def _require_admin():
        if not _admin_allowed():
            return redirect(url_for("admin_login", next=request.path))
        return None

    def _apply_display_segments(result: dict, carryover_dates_iso: list[str], week_end_date: str) -> None:
        if not result or not carryover_dates_iso or not week_end_date:
            return
        carry_dates = {date.fromisoformat(d) for d in carryover_dates_iso}
        for day in result.get("day_results", []):
            day_date_str = day.get("date")
            if not day_date_str:
                continue
            day_date = date.fromisoformat(day_date_str)
            segments = day.get("segments") or []
            display_segments = []
            cap_end = None
            if day_date in carry_dates:
                cap_end = datetime.combine(day_date + timedelta(days=1), time(0, 0))
            for seg in segments:
                start_str = seg.get("start")
                end_str = seg.get("end")
                if not start_str or not end_str:
                    continue
                start_dt = datetime.combine(day_date, datetime.strptime(start_str, "%H:%M").time())
                end_dt = datetime.combine(day_date, datetime.strptime(end_str, "%H:%M").time())
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                if cap_end:
                    if start_dt >= cap_end:
                        continue
                    if end_dt > cap_end:
                        end_dt = cap_end
                if end_dt <= start_dt:
                    continue
                display_segments.append(
                    {"start": start_dt.strftime("%H:%M"), "end": end_dt.strftime("%H:%M")}
                )
            day["display_segments"] = display_segments

    def _build_prefill_from_form(
        form, week_start_date: date, employee_name: str, normal_start: str, normal_end: str
    ) -> dict:
        days_payload = []
        for i in range(7):
            day_date = (week_start_date + timedelta(days=i)).isoformat()
            is_off = form.get(f"day_off_{i}") == "on"
            is_holiday = form.get(f"day_holiday_{i}") == "on"
            memo = (form.get(f"day_memo_{i}") or "").strip()
            segments = []
            segment_idx = 0
            while True:
                start_key = f"day_{i}_start_{segment_idx}"
                end_key = f"day_{i}_end_{segment_idx}"
                start_time = form.get(start_key)
                end_time = form.get(end_key)
                if not start_time or not end_time:
                    break
                segments.append({"start": start_time, "end": end_time})
                segment_idx += 1
            days_payload.append(
                {
                    "date": day_date,
                    "is_off": is_off,
                    "is_holiday": is_holiday,
                    "memo": memo,
                    "segments": segments,
                }
            )
        return {
            "employee_name": employee_name,
            "week_start_date": week_start_date.isoformat(),
            "normal_start": normal_start,
            "normal_end": normal_end,
            "days": days_payload,
        }

    @app.route("/calculator")
    def calculator():
        return redirect(url_for("employees"))

    @app.route("/calculator/<employee_name>")
    def calculator_for_employee(employee_name: str):
        """주간 근무 계산기 입력 폼 (직원별)"""
        # 주차 기준일이 GET 파라미터로 전달되면 사용, 없으면 저번주(지난주) 월요일로 설정
        week_start_str = request.args.get("week_start")
        week_dates = []
        
        if week_start_str:
            try:
                week_start_date = date.fromisoformat(week_start_str)
                week_start_date = week_start(week_start_date)
                for i in range(7):
                    week_dates.append(week_start_date + timedelta(days=i))
            except (ValueError, TypeError):
                # 날짜 형식 오류 시 기본값 사용 (저번주 월요일)
                pass
        else:
            # 기본값: 저번주(지난주) 월요일
            today = date.today()
            # 오늘 날짜의 주 시작일(월요일) 구하기
            current_week_start = week_start(today)
            # 저번주 월요일 = 현재 주 월요일 - 7일
            last_week_start = current_week_start - timedelta(days=7)
            for i in range(7):
                week_dates.append(last_week_start + timedelta(days=i))
        
        employees = get_employees()
        if employee_name not in employees:
            flash("직원이 존재하지 않습니다.", "danger")
            return redirect(url_for("employees"))

        return render_template(
            "calculator.html",
            week_dates=week_dates,
            employee_name=employee_name,
            prefill_data=None,
        )

    @app.route("/calculator/reload", methods=["POST"])
    def calculator_reload():
        """계산 결과에서 입력값 재불러오기"""
        input_json = request.form.get("input_json", "")
        if not input_json:
            flash("불러올 입력 데이터가 없습니다.", "danger")
            return redirect(url_for("employees"))
        try:
            prefill_data = json.loads(input_json)
        except json.JSONDecodeError:
            flash("입력 데이터 형식이 올바르지 않습니다.", "danger")
            return redirect(url_for("employees"))

        employee_name = (prefill_data.get("employee_name") or request.form.get("employee_name") or "").strip()
        if not employee_name:
            flash("직원을 선택하세요.", "danger")
            return redirect(url_for("employees"))

        week_dates = []
        week_start_str = prefill_data.get("week_start_date")
        if week_start_str:
            try:
                week_start_date = date.fromisoformat(week_start_str)
                week_start_date = week_start(week_start_date)
                for i in range(7):
                    week_dates.append(week_start_date + timedelta(days=i))
            except (ValueError, TypeError):
                pass
        if not week_dates:
            today = date.today()
            current_week_start = week_start(today)
            last_week_start = current_week_start - timedelta(days=7)
            for i in range(7):
                week_dates.append(last_week_start + timedelta(days=i))

        return render_template(
            "calculator.html",
            week_dates=week_dates,
            employee_name=employee_name,
            normal_start=prefill_data.get("normal_start"),
            normal_end=prefill_data.get("normal_end"),
            prefill_data=prefill_data,
        )

    @app.route("/employees")
    def employees():
        """직원별 저장된 계산 목록"""
        overview = get_employee_overview()
        return render_template("employees.html", employees=overview)


    @app.route("/admin/employees", methods=["GET"])
    def admin_employees():
        require = _require_admin()
        if require:
            return require
        items = get_employee_admin_list()
        return render_template("admin_employees.html", items=items)

    @app.route("/admin/employees/add", methods=["POST"])
    def admin_employee_add():
        require = _require_admin()
        if require:
            return require
        name = (request.form.get("employee_name") or "").strip()
        if not name:
            flash("직원명을 입력하세요.", "danger")
            return redirect(url_for("admin_employees"))
        if get_employee_id(name):
            flash("이미 등록된 직원입니다.", "warning")
            return redirect(url_for("admin_employees"))
        add_employee(name)
        flash("직원이 추가되었습니다.", "success")
        return redirect(url_for("admin_employees"))

    @app.route("/admin/employees/<int:employee_id>/delete", methods=["POST"])
    def admin_employee_delete(employee_id: int):
        require = _require_admin()
        if require:
            return require
        password = request.form.get("password", "")
        if password != ADMIN_PASSWORD:
            flash("비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("admin_employees"))
        calc_count, trash_count = get_employee_usage_counts(employee_id)
        if calc_count > 0 or trash_count > 0:
            flash("해당 직원의 계산 내역이 있어 삭제할 수 없습니다.", "warning")
            return redirect(url_for("admin_employees"))
        delete_employee_by_id(employee_id)
        flash("직원이 삭제되었습니다.", "success")
        return redirect(url_for("admin_employees"))

    @app.route("/employees/<employee_name>")
    def employee_detail(employee_name: str):
        """직원별 계산 내역 상세"""
        review_mode = request.args.get("review") == "1"
        selected_year = request.args.get("year")
        selected_ym = request.args.get("ym")
        calculations = get_employee_calculations(employee_name)
        calc_items = []
        for row in calculations:
            result_json = json.loads(row["result_json"])
            input_json = json.loads(row["input_json"])
            calc_items.append(
                {
                    "id": row["id"],
                    "week_start_date": row["week_start_date"],
                    "week_end_date": row["week_end_date"],
                    "normal_start": row["normal_start"],
                    "normal_end": row["normal_end"],
                    "created_at": row["created_at"],
                    "week_total_min": result_json.get("week_total_min", 0),
                    "bucket_15_total": result_json.get("bucket_15_total", 0),
                    "bucket_20_total": result_json.get("bucket_20_total", 0),
                    "bucket_25_total": result_json.get("bucket_25_total", 0),
                    "needs_review": bool(row["needs_review"]) if "needs_review" in row.keys() else False,
                    "auto_carryover": bool(input_json.get("auto_carryover")),
                    "carryover_from": input_json.get("carryover_from"),
                }
            )

        review_items = [item for item in calc_items if item.get("needs_review")]
        normal_items = [item for item in calc_items if not item.get("needs_review")]
        list_items = review_items if review_mode else normal_items
        year_months = sorted({item["week_start_date"][:7] for item in list_items}, reverse=True)
        year_month_groups: dict[str, list[str]] = {}
        for ym in year_months:
            year, month = ym.split("-", 1)
            year_month_groups.setdefault(year, []).append(month)
        for year in year_month_groups:
            year_month_groups[year] = sorted(set(year_month_groups[year]))
        if selected_year and selected_year in year_month_groups:
            list_items = [item for item in list_items if item["week_start_date"].startswith(selected_year)]
        if selected_ym:
            list_items = [item for item in list_items if item["week_start_date"].startswith(selected_ym)]
        week_counts: dict[str, int] = {}
        for item in list_items:
            week_start_key = item["week_start_date"]
            week_counts[week_start_key] = week_counts.get(week_start_key, 0) + 1

        # 집계용 총합 (현재 필터/뷰에 표시되는 항목만 합산)
        total_week_total_min = sum(item["week_total_min"] for item in list_items) if list_items else 0
        total_bucket_15_min = sum(item["bucket_15_total"] for item in list_items) if list_items else 0
        total_bucket_20_min = sum(item["bucket_20_total"] for item in list_items) if list_items else 0
        total_bucket_25_min = sum(item["bucket_25_total"] for item in list_items) if list_items else 0

        selected_calc = None
        merged_calc = None
        calc_id = request.args.get("calc_id")
        merge_week_start = request.args.get("merge_week_start")
        if calc_id and calc_id.isdigit():
            row = get_calculation_by_id(int(calc_id))
            if row and row["employee_name"] == employee_name:
                row_is_review = bool(row["needs_review"]) if "needs_review" in row.keys() else False
                if review_mode != row_is_review:
                    flash("선택한 내역은 다른 목록에 있습니다.", "warning")
                    return redirect(
                        url_for(
                            "employee_detail",
                            employee_name=employee_name,
                            calc_id=calc_id,
                            review="1" if row_is_review else None,
                        )
                    )
                selected_result = json.loads(row["result_json"])
                weekdays = ['월', '화', '수', '목', '금', '토', '일']
                for day in selected_result.get("day_results", []):
                    try:
                        day_date = date.fromisoformat(day.get("date", ""))
                        day["weekday"] = weekdays[day_date.weekday()]
                    except (ValueError, TypeError):
                        day["weekday"] = ""
                input_payload = json.loads(row["input_json"])
                _apply_display_segments(
                    selected_result,
                    input_payload.get("carryover_dates_iso", []),
                    row["week_end_date"],
                )
                selected_calc = {
                    "id": row["id"],
                    "week_start_date": row["week_start_date"],
                    "week_end_date": row["week_end_date"],
                    "normal_start": row["normal_start"],
                    "normal_end": row["normal_end"],
                    "created_at": row["created_at"],
                    "input": input_payload,
                    "result": selected_result,
                    "result_json": json.dumps(selected_result, ensure_ascii=False),
                    "auto_carryover": bool(input_payload.get("auto_carryover")),
                    "carryover_from": input_payload.get("carryover_from"),
                    "carryover_notice": input_payload.get("carryover_notice"),
                    "carryover_dates_iso": input_payload.get("carryover_dates_iso", []),
                    "carryover_min": input_payload.get("carryover_min", 0),
                }
        elif merge_week_start:
            if review_mode:
                flash("수정 필요 항목에서는 합산할 수 없습니다.", "warning")
                return redirect(url_for("employee_review", employee_name=employee_name))
            same_week_rows = [
                row for row in calculations
                if row["week_start_date"] == merge_week_start
            ]
            if same_week_rows:
                base_week_start = date.fromisoformat(merge_week_start)
                base_week_end = base_week_start + timedelta(days=6)
                weekdays = ['월', '화', '수', '목', '금', '토', '일']
                auto_rows = []

                merged_days: list[DayWork] = []
                merged_input_days: list[dict] = []
                for i in range(7):
                    current_date = base_week_start + timedelta(days=i)
                    merged_segments: list[WorkSegment] = []
                    merged_memos: list[str] = []
                    is_holiday = False
                    for row in same_week_rows:
                        input_json = json.loads(row["input_json"])
                        if input_json.get("auto_carryover"):
                            auto_rows.append(row)
                        for day in input_json.get("days", []):
                            if day.get("date") != current_date.isoformat():
                                continue
                            is_holiday = is_holiday or bool(day.get("is_holiday"))
                            memo = (day.get("memo") or "").strip()
                            if memo:
                                merged_memos.append(memo)
                            for seg in day.get("segments", []):
                                start = seg.get("start")
                                end = seg.get("end")
                                if start and end:
                                    merged_segments.append(WorkSegment(start, end, is_holiday=False))

                    merged_day = DayWork(current_date, merged_segments, is_holiday=is_holiday)
                    merged_day.memo = " / ".join(merged_memos) if merged_memos else ""
                    merged_days.append(merged_day)
                    merged_input_days.append(
                        {
                            "date": current_date.isoformat(),
                            "is_off": merged_day.is_off,
                            "is_holiday": is_holiday,
                            "memo": merged_day.memo,
                            "segments": [
                                {
                                    "start": seg.start_time.strftime("%H:%M"),
                                    "end": seg.end_time.strftime("%H:%M"),
                                }
                                for seg in merged_segments
                            ],
                        }
                    )

                normal_start = same_week_rows[0]["normal_start"]
                normal_end = same_week_rows[0]["normal_end"]
                normal_start_t = datetime.strptime(normal_start, "%H:%M").time()
                merged_week = WeekWork(base_week_start, merged_days)
                merged_result = calculate_week_work(merged_week, normal_start, normal_end)
                merged_exceeds_40 = False

                # 합산 결과에도 근무 시간/휴게 정보 추가
                for i, day_result in enumerate(merged_result.get("day_results", [])):
                    if i < len(merged_days):
                        day_work = merged_days[i]
                        if not day_result.get("is_off", False):
                            segments_info = []
                            work_times_str = ""
                            start_times = []
                            end_times = []
                            for seg in day_work.segments:
                                start_str = seg.start_time.strftime("%H:%M")
                                end_str = seg.end_time.strftime("%H:%M")
                                segments_info.append({"start": start_str, "end": end_str})
                                start_times.append(start_str)
                                end_times.append(end_str)
                            day_result["segments"] = segments_info
                            if start_times and end_times:
                                day_result["work_times_str"] = ",".join(start_times) + "|" + ",".join(end_times)
                            else:
                                day_result["work_times_str"] = ""

                            break_segments = []
                            if "timeline" in day_result:
                                for timeline_seg in day_result["timeline"]:
                                    if timeline_seg.get("kind") == "break":
                                        label = timeline_seg.get("label", "")
                                        if "~" in label:
                                            break_segments.append(_format_break_label(label))
                            day_result["break_times"] = break_segments
                        else:
                            day_result["segments"] = []
                            day_result["work_times_str"] = ""
                            day_result["break_times"] = []

                # 이월 자동 생성 데이터는 이전 ERP 결과 기반 타임라인을 합산에 적용
                def parse_timeline_label(base_date: date, label: str) -> Optional[Tuple[datetime, datetime]]:
                    clean_label = label.replace("[휴일] ", "").strip()
                    if "~" not in clean_label:
                        return None
                    left, right = clean_label.split("~", 1)
                    left = left.strip()
                    right = right.strip()

                    def parse_part(part: str) -> Tuple[Optional[int], Optional[int], int, int]:
                        if "/" in part:
                            date_part, time_part = part.split(" ", 1)
                            month_str, day_str = date_part.split("/", 1)
                            hour_str, min_str = time_part.split(":", 1)
                            return int(month_str), int(day_str), int(hour_str), int(min_str)
                        hour_str, min_str = part.split(":", 1)
                        return None, None, int(hour_str), int(min_str)

                    l_month, l_day, l_hour, l_min = parse_part(left)
                    r_month, r_day, r_hour, r_min = parse_part(right)

                    if l_month is None:
                        start_dt = datetime.combine(base_date, time(l_hour, l_min))
                    else:
                        start_dt = datetime(base_date.year, l_month, l_day, l_hour, l_min)

                    if r_month is None:
                        end_dt = datetime.combine(start_dt.date(), time(r_hour, r_min))
                        if end_dt <= start_dt:
                            end_dt += timedelta(days=1)
                    else:
                        end_year = base_date.year
                        if r_month < (l_month or start_dt.month):
                            end_year += 1
                        end_dt = datetime(end_year, r_month, r_day, r_hour, r_min)

                    return start_dt, end_dt

                if auto_rows:
                    override_by_date: dict[date, list[dict]] = {}
                    carryover_ranges_by_date: dict[date, list[tuple[datetime, datetime]]] = {}
                    for row in auto_rows:
                        result_json = json.loads(row["result_json"])
                        for day in result_json.get("day_results", []):
                            day_date_str = day.get("date")
                            if not day_date_str:
                                continue
                            day_date = date.fromisoformat(day_date_str)
                            for seg in day.get("timeline", []):
                                parsed = parse_timeline_label(day_date, seg.get("label", ""))
                                if not parsed:
                                    continue
                                start_dt, end_dt = parsed
                                if day_date not in override_by_date:
                                    override_by_date[day_date] = []
                                effective_kind = seg.get("original_kind") or seg.get("kind", "base")
                                if effective_kind == "carry":
                                    effective_kind = "base"
                                effective_calc = seg.get("original_calculation") or seg.get("calculation", "")
                                override_by_date[day_date].append(
                                    {
                                        "start_dt": start_dt,
                                        "end_dt": end_dt,
                                        "kind": effective_kind,
                                        "calculation": effective_calc,
                                    }
                                )
                                carryover_ranges_by_date.setdefault(day_date, []).append((start_dt, end_dt))

                    for day_result in merged_result.get("day_results", []):
                        day_date_str = day_result.get("date")
                        if not day_date_str:
                            continue
                        day_date = date.fromisoformat(day_date_str)
                        if day_date not in override_by_date:
                            continue

                        base_segments = day_result.get("timeline", [])
                        minute_map: dict[datetime, dict] = {}

                        for seg in base_segments:
                            parsed = parse_timeline_label(day_date, seg.get("label", ""))
                            if not parsed:
                                continue
                            start_dt, end_dt = parsed
                            current = start_dt
                            while current < end_dt:
                                minute_map[current] = {
                                    "kind": seg.get("kind", "base"),
                                    "calculation": seg.get("calculation", ""),
                                }
                                current += timedelta(minutes=1)

                        for seg in override_by_date[day_date]:
                            current = seg["start_dt"]
                            while current < seg["end_dt"]:
                                minute_map[current] = {
                                    "kind": seg.get("kind", "base"),
                                    "calculation": seg.get("calculation", ""),
                                    "carryover": True,
                                }
                                current += timedelta(minutes=1)

                        if not minute_map:
                            continue

                        sorted_minutes = sorted(minute_map.keys())
                        work_min = 0
                        break_min = 0
                        overtime_min = 0
                        bucket_15 = 0
                        bucket_20 = 0
                        bucket_25 = 0
                        timeline_segments = []
                        max_end_minutes = 0
                        base_dt = datetime.combine(day_date, time(0, 0))

                        i = 0
                        while i < len(sorted_minutes):
                            start_dt = sorted_minutes[i]
                            info = minute_map[start_dt]
                            kind = info.get("kind", "base")
                            calc = info.get("calculation", "")

                            j = i + 1
                            while j < len(sorted_minutes):
                                next_dt = sorted_minutes[j]
                                if next_dt != sorted_minutes[j - 1] + timedelta(minutes=1):
                                    break
                                next_info = minute_map[next_dt]
                                if next_info.get("kind") != kind:
                                    break
                                j += 1

                            end_dt = sorted_minutes[j - 1] + timedelta(minutes=1)
                            duration_min = int((end_dt - start_dt).total_seconds() // 60)
                            start_minutes = int((start_dt - base_dt).total_seconds() // 60)
                            end_minutes = start_minutes + duration_min
                            max_end_minutes = max(max_end_minutes, end_minutes)

                            if kind == "break":
                                break_min += duration_min
                            else:
                                work_min += duration_min
                                if "연장근로" in (calc or ""):
                                    overtime_min += duration_min
                                if kind == "m15":
                                    bucket_15 += duration_min
                                elif kind == "m20":
                                    bucket_20 += duration_min
                                elif kind == "m25":
                                    bucket_25 += duration_min

                            label = (
                                f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
                                if start_dt.date() == end_dt.date()
                                else f"{start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%m/%d %H:%M')}"
                            )
                            timeline_segments.append(
                                {
                                    "start_minutes": start_minutes,
                                    "duration_min": duration_min,
                                    "kind": kind,
                                    "label": label,
                                    "calculation": calc,
                                }
                            )

                            i = j

                        if max_end_minutes > 1440:
                            max_timeline_minutes = ((max_end_minutes - 1) // 360 + 1) * 360
                            max_timeline_minutes = min(max_timeline_minutes, 2880)
                        else:
                            max_timeline_minutes = 1440

                        for seg in timeline_segments:
                            seg["left"] = round((seg["start_minutes"] / max_timeline_minutes) * 100, 4)
                            seg["width"] = round((seg["duration_min"] / max_timeline_minutes) * 100, 4)
                            del seg["start_minutes"]
                            del seg["duration_min"]

                        day_result["work_min"] = work_min
                        day_result["break_min"] = break_min
                        day_result["overtime_min"] = overtime_min
                        day_result["bucket_15_min"] = bucket_15
                        day_result["bucket_20_min"] = bucket_20
                        day_result["bucket_25_min"] = bucket_25
                        day_result["timeline"] = timeline_segments
                        day_result["max_timeline_hours"] = max_timeline_minutes // 60
                        day_result["has_admin_interpretation"] = False

                merged_bucket_15 = sum(day.get("bucket_15_min", 0) for day in merged_result.get("day_results", []))
                merged_bucket_20 = sum(day.get("bucket_20_min", 0) for day in merged_result.get("day_results", []))
                merged_bucket_25 = sum(day.get("bucket_25_min", 0) for day in merged_result.get("day_results", []))
                merged_base_min = 0
                raw_base_min = 0
                for day in merged_result.get("day_results", []):
                    day_date_str = day.get("date")
                    if not day_date_str:
                        continue
                    day_date = date.fromisoformat(day_date_str)
                    base_minutes = 0
                    for seg in day.get("timeline", []):
                        kind = seg.get("kind")
                        calc_text = seg.get("calculation") or ""
                        is_base_like = False
                        if kind == "base":
                            is_base_like = True
                        elif kind == "m15":
                            if ("연장근로" in calc_text) and ("야간근로" not in calc_text) and ("휴일근로" not in calc_text):
                                is_base_like = True
                        if not is_base_like:
                            continue
                        parsed = parse_timeline_label(day_date, seg.get("label", ""))
                        if not parsed:
                            continue
                        start_dt, end_dt = parsed
                        base_minutes += int((end_dt - start_dt).total_seconds() // 60)
                    raw_base_min += min(base_minutes, DAY_LIMIT_MIN)
                merged_exceeds_40 = raw_base_min > WEEK_LIMIT_40_MIN
                merged_base_min = min(raw_base_min, WEEK_LIMIT_40_MIN)

                # 주 40시간 기준(1.0배) 초과분은 시간 순서대로 연장 처리
                base_like_minutes: list[datetime] = []
                base_like_count_by_date: dict[date, int] = {}
                for day_result in merged_result.get("day_results", []):
                    day_date_str = day_result.get("date")
                    if not day_date_str:
                        continue
                    day_date = date.fromisoformat(day_date_str)
                    carry_ranges = carryover_ranges_by_date.get(day_date, [])
                    for seg in day_result.get("timeline", []):
                        kind = seg.get("kind")
                        if kind == "break":
                            continue
                        calc_text = (seg.get("calculation") or "").strip()
                        if "연장근로" in calc_text:
                            continue
                        parsed = parse_timeline_label(day_date, seg.get("label", ""))
                        if not parsed:
                            continue
                        start_dt, end_dt = parsed
                        current = start_dt
                        while current < end_dt:
                            base_date = current.date()
                            if current.time() < normal_start_t:
                                base_date = base_date - timedelta(days=1)
                            if base_like_count_by_date.get(base_date, 0) < DAY_LIMIT_MIN:
                                base_like_minutes.append(current)
                                base_like_count_by_date[base_date] = base_like_count_by_date.get(base_date, 0) + 1
                            current += timedelta(minutes=1)

                weekly_overtime_minutes: set[datetime] = set()
                if merged_exceeds_40:
                    sorted_base_minutes = sorted(base_like_minutes)
                    threshold = WEEK_LIMIT_40_MIN
                    weekly_overtime_minutes = set(sorted_base_minutes[threshold:])

                for day_result in merged_result.get("day_results", []):
                    day_date_str = day_result.get("date")
                    if not day_date_str:
                        continue
                    day_date = date.fromisoformat(day_date_str)
                    base_dt = datetime.combine(day_date, time(0, 0))
                    minute_map: dict[datetime, dict] = {}

                    day_carryover_ranges = carryover_ranges_by_date.get(day_date, [])
                    for seg in day_result.get("timeline", []):
                        parsed = parse_timeline_label(day_date, seg.get("label", ""))
                        if not parsed:
                            continue
                        start_dt, end_dt = parsed
                        current = start_dt
                        while current < end_dt:
                            is_carry = False
                            for r_start, r_end in day_carryover_ranges:
                                if r_start <= current < r_end:
                                    is_carry = True
                                    break
                            minute_map[current] = {
                                "kind": seg.get("kind", "base"),
                                "calculation": seg.get("calculation", ""),
                                "carryover": is_carry,
                            }
                            current += timedelta(minutes=1)

                    # 기존 연장근로(연장만) 표기는 base로 환원
                    for minute_dt, info in list(minute_map.items()):
                        if info.get("carryover"):
                            continue
                        if info.get("kind") == "m15":
                            calc_text = info.get("calculation") or ""
                            if ("연장근로" in calc_text) and ("야간근로" not in calc_text) and ("휴일근로" not in calc_text):
                                minute_map[minute_dt] = {
                                    "kind": "base",
                                    "calculation": "기본 1.0배",
                                    "carryover": False,
                                }

                    # 일일 8시간 초과분은 시간 순서대로 연장 처리 (base 구간만)
                    day_work_minutes = []
                    for dt in sorted(minute_map.keys()):
                        info = minute_map[dt]
                        if info["kind"] == "break":
                            continue
                        if info.get("carryover"):
                            calc_text = info.get("calculation") or ""
                            if "연장근로" in calc_text:
                                continue
                        day_work_minutes.append(dt)
                    for idx, minute_dt in enumerate(day_work_minutes):
                        if idx >= DAY_LIMIT_MIN:
                            if minute_map[minute_dt].get("carryover"):
                                continue
                            if minute_map[minute_dt]["kind"] == "base":
                                minute_map[minute_dt] = {
                                    "kind": "m15",
                                    "calculation": "기본 1.0배\n+ 연장근로 +50%\n= 총 1.5배",
                                    "carryover": False,
                                }

                    # 주 40시간 초과 기준 분을 1.5배로 전환 (base 구간만)
                    if merged_exceeds_40:
                        for minute_dt in weekly_overtime_minutes:
                            if minute_dt.date() != day_date:
                                continue
                            current_info = minute_map.get(minute_dt)
                            if not current_info:
                                continue
                            if current_info.get("carryover"):
                                continue
                            if current_info.get("kind") == "base":
                                minute_map[minute_dt] = {
                                    "kind": "m15",
                                    "calculation": "기본 1.0배\n+ 연장근로 +50%\n= 총 1.5배",
                                    "carryover": False,
                                }

                    if not minute_map:
                        continue

                    sorted_minutes = sorted(minute_map.keys())
                    work_min = 0
                    break_min = 0
                    bucket_15 = 0
                    bucket_20 = 0
                    bucket_25 = 0
                    timeline_segments = []
                    max_end_minutes = 0

                    i = 0
                    while i < len(sorted_minutes):
                        start_dt = sorted_minutes[i]
                        info = minute_map[start_dt]
                        kind = info.get("kind", "base")
                        calc = info.get("calculation", "")

                        j = i + 1
                        while j < len(sorted_minutes):
                            next_dt = sorted_minutes[j]
                            if next_dt != sorted_minutes[j - 1] + timedelta(minutes=1):
                                break
                            next_info = minute_map[next_dt]
                            if next_info.get("kind") != kind:
                                break
                            j += 1

                        end_dt = sorted_minutes[j - 1] + timedelta(minutes=1)
                        duration_min = int((end_dt - start_dt).total_seconds() // 60)
                        start_minutes = int((start_dt - base_dt).total_seconds() // 60)
                        end_minutes = start_minutes + duration_min
                        max_end_minutes = max(max_end_minutes, end_minutes)

                        if kind == "break":
                            break_min += duration_min
                        else:
                            work_min += duration_min
                            if kind == "m15":
                                bucket_15 += duration_min
                            elif kind == "m20":
                                bucket_20 += duration_min
                            elif kind == "m25":
                                bucket_25 += duration_min

                        label = (
                            f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
                            if start_dt.date() == end_dt.date()
                            else f"{start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%m/%d %H:%M')}"
                        )
                        timeline_segments.append(
                            {
                                "start_minutes": start_minutes,
                                "duration_min": duration_min,
                                "kind": kind,
                                "label": label,
                                "calculation": calc,
                            }
                        )
                        i = j

                    if max_end_minutes > 1440:
                        max_timeline_minutes = ((max_end_minutes - 1) // 360 + 1) * 360
                        max_timeline_minutes = min(max_timeline_minutes, 2880)
                    else:
                        max_timeline_minutes = 1440

                    for seg in timeline_segments:
                        seg["left"] = round((seg["start_minutes"] / max_timeline_minutes) * 100, 4)
                        seg["width"] = round((seg["duration_min"] / max_timeline_minutes) * 100, 4)
                        del seg["start_minutes"]
                        del seg["duration_min"]

                    day_result["work_min"] = work_min
                    day_result["break_min"] = break_min
                    day_result["bucket_15_min"] = bucket_15
                    day_result["bucket_20_min"] = bucket_20
                    day_result["bucket_25_min"] = bucket_25
                    day_result["timeline"] = timeline_segments
                    day_result["max_timeline_hours"] = max_timeline_minutes // 60
                    day_result["has_admin_interpretation"] = False
                    day_result["break_times"] = [
                        _format_break_label(seg["label"]) for seg in timeline_segments
                        if seg.get("kind") == "break" and "~" in seg.get("label", "")
                    ]

                    # bucket 재계산
                    bucket_15 = 0
                    bucket_20 = 0
                    bucket_25 = 0
                    for seg in day_result.get("timeline", []):
                        kind = seg.get("kind")
                        if kind in ["m15", "m20", "m25"]:
                            parsed = parse_timeline_label(day_date, seg.get("label", ""))
                            if not parsed:
                                continue
                            start_dt, end_dt = parsed
                            duration_min = int((end_dt - start_dt).total_seconds() // 60)
                            if kind == "m15":
                                bucket_15 += duration_min
                            elif kind == "m20":
                                bucket_20 += duration_min
                            elif kind == "m25":
                                bucket_25 += duration_min
                    day_result["bucket_15_min"] = bucket_15
                    day_result["bucket_20_min"] = bucket_20
                    day_result["bucket_25_min"] = bucket_25
                merged_bucket_15 = sum(day.get("bucket_15_min", 0) for day in merged_result.get("day_results", []))
                merged_bucket_20 = sum(day.get("bucket_20_min", 0) for day in merged_result.get("day_results", []))
                merged_bucket_25 = sum(day.get("bucket_25_min", 0) for day in merged_result.get("day_results", []))
                merged_week_total = sum(day.get("work_min", 0) for day in merged_result.get("day_results", []))
                merged_week_overtime = sum(day.get("overtime_min", 0) for day in merged_result.get("day_results", []))
                merged_result["bucket_15_total"] = merged_bucket_15
                merged_result["bucket_20_total"] = merged_bucket_20
                merged_result["bucket_25_total"] = merged_bucket_25
                merged_result["week_total_min"] = merged_week_total
                merged_result["week_overtime_min"] = merged_week_overtime
                merged_result["week_base_min"] = merged_base_min
                merged_result["exceeds_40"] = merged_exceeds_40
                for day in merged_result.get("day_results", []):
                    try:
                        day_date = date.fromisoformat(day.get("date", ""))
                        day["weekday"] = weekdays[day_date.weekday()]
                    except (ValueError, TypeError):
                        day["weekday"] = ""
                _apply_display_segments(merged_result, [], base_week_end.isoformat())
                merged_calc = {
                    "id": "merged",
                    "week_start_date": merge_week_start,
                    "week_end_date": base_week_end.isoformat(),
                    "normal_start": normal_start,
                    "normal_end": normal_end,
                    "created_at": "",
                    "input": {
                        "employee_name": employee_name,
                        "week_start_date": merge_week_start,
                        "week_end_date": base_week_end.isoformat(),
                        "normal_start": normal_start,
                        "normal_end": normal_end,
                        "days": merged_input_days,
                    },
                    "result": merged_result,
                    "result_json": json.dumps(merged_result, ensure_ascii=False),
                    "auto_carryover": False,
                    "carryover_from": None,
                    "is_merged": True,
                    "merged_count": len(same_week_rows),
                }

        return render_template(
            "employee_detail.html",
            employee_name=employee_name,
            calculations=list_items,
            review_items=review_items,
            normal_items=normal_items,
            selected_calc=selected_calc or merged_calc,
            week_counts=week_counts,
            review_mode=review_mode,
            selected_year=selected_year,
            selected_ym=selected_ym,
            year_months=year_months,
            year_month_groups=year_month_groups,
            agg_total_min=total_week_total_min,
            agg_bucket_15_min=total_bucket_15_min,
            agg_bucket_20_min=total_bucket_20_min,
            agg_bucket_25_min=total_bucket_25_min,
        )

    @app.route("/employees/<employee_name>/review")
    def employee_review(employee_name: str):
        """직원별 수정 필요 내역"""
        selected_year = request.args.get("year")
        selected_ym = request.args.get("ym")
        calculations = get_employee_calculations(employee_name)
        review_items = []
        for row in calculations:
            result_json = json.loads(row["result_json"])
            input_json = json.loads(row["input_json"])
            if not (row["needs_review"] if "needs_review" in row.keys() else False):
                continue
            review_items.append(
                {
                    "id": row["id"],
                    "week_start_date": row["week_start_date"],
                    "week_end_date": row["week_end_date"],
                    "normal_start": row["normal_start"],
                    "normal_end": row["normal_end"],
                    "week_total_min": result_json.get("week_total_min", 0),
                    "bucket_15_total": result_json.get("bucket_15_total", 0),
                    "bucket_20_total": result_json.get("bucket_20_total", 0),
                    "bucket_25_total": result_json.get("bucket_25_total", 0),
                    "auto_carryover": bool(input_json.get("auto_carryover")),
                }
            )
        year_months = sorted({item["week_start_date"][:7] for item in review_items}, reverse=True)
        year_month_groups: dict[str, list[str]] = {}
        for ym in year_months:
            year, month = ym.split("-", 1)
            year_month_groups.setdefault(year, []).append(month)
        for year in year_month_groups:
            year_month_groups[year] = sorted(set(year_month_groups[year]))
        if selected_year and selected_year in year_month_groups:
            review_items = [item for item in review_items if item["week_start_date"].startswith(selected_year)]
        if selected_ym:
            review_items = [item for item in review_items if item["week_start_date"].startswith(selected_ym)]
        return render_template(
            "employee_review.html",
            employee_name=employee_name,
            review_items=review_items,
            year_months=year_months,
            year_month_groups=year_month_groups,
            selected_year=selected_year,
            selected_ym=selected_ym,
        )

    @app.route("/employees/<employee_name>/delete", methods=["POST"])
    def employee_delete(employee_name: str):
        calc_id = request.form.get("calc_id")
        if not calc_id or not calc_id.isdigit():
            flash("삭제 대상이 올바르지 않습니다.", "danger")
            return redirect(url_for("employee_detail", employee_name=employee_name))

        row = get_calculation_by_id(int(calc_id))
        if not row or row["employee_name"] != employee_name:
            flash("삭제 대상이 존재하지 않습니다.", "danger")
            return redirect(url_for("employee_detail", employee_name=employee_name))

        move_calculation_to_trash(int(calc_id))
        flash("삭제 내역을 보관함으로 이동했습니다.", "success")
        return redirect(url_for("employee_detail", employee_name=employee_name))

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            password = request.form.get("password", "")
            if password == ADMIN_PASSWORD:
                session["admin_ok"] = True
                next_url = request.args.get("next") or url_for("admin_trash")
                return redirect(next_url)
            flash("비밀번호가 올바르지 않습니다.", "danger")
        return render_template("admin_login.html")

    @app.route("/admin/logout", methods=["POST"])
    def admin_logout():
        session.pop("admin_ok", None)
        flash("관리자 로그아웃되었습니다.", "success")
        return redirect(url_for("employees"))

    @app.route("/admin/trash")
    def admin_trash():
        require = _require_admin()
        if require:
            return require
        selected_year = request.args.get("year")
        selected_ym = request.args.get("ym")
        selected_employee = request.args.get("employee")
        rows = get_deleted_calculations()
        items = []
        for row in rows:
            try:
                result_json = json.loads(row["result_json"])
            except (TypeError, json.JSONDecodeError):
                result_json = {}
            items.append(
                {
                    "id": row["id"],
                    "employee_name": row["employee_name"],
                    "week_start_date": row["week_start_date"],
                    "week_end_date": row["week_end_date"],
                    "normal_start": row["normal_start"],
                    "normal_end": row["normal_end"],
                    "created_at": row["created_at"],
                    "deleted_at": row["deleted_at"],
                    "week_total_min": result_json.get("week_total_min", 0),
                    "bucket_15_total": result_json.get("bucket_15_total", 0),
                    "bucket_20_total": result_json.get("bucket_20_total", 0),
                    "bucket_25_total": result_json.get("bucket_25_total", 0),
                }
            )
        employee_names = sorted({item["employee_name"] for item in items})
        year_months = sorted({item["week_start_date"][:7] for item in items}, reverse=True)
        year_month_groups: dict[str, list[str]] = {}
        for ym in year_months:
            year, month = ym.split("-", 1)
            year_month_groups.setdefault(year, []).append(month)
        for year in year_month_groups:
            year_month_groups[year] = sorted(set(year_month_groups[year]))
        if selected_employee:
            items = [item for item in items if item["employee_name"] == selected_employee]
        if selected_year and selected_year in year_month_groups:
            items = [item for item in items if item["week_start_date"].startswith(selected_year)]
        if selected_ym:
            items = [item for item in items if item["week_start_date"].startswith(selected_ym)]
        return render_template(
            "admin_trash.html",
            items=items,
            year_month_groups=year_month_groups,
            selected_year=selected_year,
            selected_ym=selected_ym,
            employee_names=employee_names,
            selected_employee=selected_employee,
        )

    @app.route("/admin/trash/<int:trash_id>")
    def admin_trash_detail(trash_id: int):
        require = _require_admin()
        if require:
            return require
        row = get_deleted_calculation_by_id(trash_id)
        if not row:
            flash("보관함 항목이 존재하지 않습니다.", "danger")
            return redirect(url_for("admin_trash"))

        selected_result = json.loads(row["result_json"])
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        for day in selected_result.get("day_results", []):
            try:
                day_date = date.fromisoformat(day.get("date", ""))
                day["weekday"] = weekdays[day_date.weekday()]
            except (ValueError, TypeError):
                day["weekday"] = ""

        input_payload = json.loads(row["input_json"])
        _apply_display_segments(
            selected_result,
            input_payload.get("carryover_dates_iso", []),
            row["week_end_date"],
        )
        selected_calc = {
            "id": row["id"],
            "week_start_date": row["week_start_date"],
            "week_end_date": row["week_end_date"],
            "normal_start": row["normal_start"],
            "normal_end": row["normal_end"],
            "created_at": row["created_at"],
            "input": input_payload,
            "result": selected_result,
            "result_json": json.dumps(selected_result, ensure_ascii=False),
            "auto_carryover": bool(input_payload.get("auto_carryover")),
            "carryover_from": input_payload.get("carryover_from"),
            "carryover_notice": input_payload.get("carryover_notice"),
            "carryover_dates_iso": input_payload.get("carryover_dates_iso", []),
            "carryover_min": input_payload.get("carryover_min", 0),
        }

        return render_template(
            "employee_detail.html",
            employee_name=row["employee_name"],
            calculations=[],
            selected_calc=selected_calc,
            week_counts={},
            admin_view=True,
            back_url=url_for("admin_trash"),
        )

    @app.route("/admin/trash/<int:trash_id>/restore", methods=["POST"])
    def admin_trash_restore(trash_id: int):
        require = _require_admin()
        if require:
            return require
        restore_deleted_calculation(trash_id)
        flash("보관함 내역을 복원했습니다.", "success")
        return redirect(url_for("admin_trash"))

    @app.route("/admin/trash/<int:trash_id>/purge", methods=["POST"])
    def admin_trash_purge(trash_id: int):
        require = _require_admin()
        if require:
            return require
        purge_deleted_calculation(trash_id)
        flash("보관함 내역을 영구 삭제했습니다.", "success")
        return redirect(url_for("admin_trash"))

    @app.route("/calculator/result", methods=["POST"])
    def calculator_result():
        """주간 근무 계산 결과"""
        try:
            # 주차 기준일
            week_start_str = request.form.get("week_start")
            if not week_start_str:
                flash("주차 기준일을 선택하세요.", "danger")
                return redirect(url_for("calculator"))
            
            week_start_date = date.fromisoformat(week_start_str)
            # 월요일로 조정
            week_start_date = week_start(week_start_date)
            
            # 직원 선택
            employee_name = (request.form.get("employee_name") or "").strip()
            if not employee_name:
                flash("직원을 선택하세요.", "danger")
                return redirect(url_for("calculator"))

            # 정상 근무 시간
            normal_start = request.form.get("normal_start", "09:00")
            normal_end = request.form.get("normal_end", "18:00")
            week_dates = [week_start_date + timedelta(days=i) for i in range(7)]
            
            # 주간 근무 데이터 수집
            weekdays = ['월', '화', '수', '목', '금', '토', '일']
            days: list[DayWork] = []
            
            for i in range(7):
                current_date = week_start_date + timedelta(days=i)
                
                # 휴일 체크 (근무 안함이어도 휴일 정보는 유지해야 함)
                is_holiday = request.form.get(f"day_holiday_{i}") == "on"
                
                # 근무 안함 체크
                is_off = request.form.get(f"day_off_{i}") == "on"
                if is_off:
                    # 근무 안함이어도 휴일 정보는 유지 (날짜 경계를 넘는 근무의 휴일 판단에 필요)
                    days.append(DayWork(current_date, [], is_holiday=is_holiday))
                    continue
                
                # 메모 수집
                day_memo = request.form.get(f"day_memo_{i}", "").strip()
                
                # 시간대 세그먼트 수집
                segments: list[WorkSegment] = []
                segment_idx = 0
                
                while True:
                    start_key = f"day_{i}_start_{segment_idx}"
                    end_key = f"day_{i}_end_{segment_idx}"
                    
                    start_time = request.form.get(start_key)
                    end_time = request.form.get(end_key)
                    
                    if not start_time or not end_time:
                        break
                    
                    # 세그먼트별 휴일은 제거 (날짜 전체 휴일만 사용)
                    try:
                        segments.append(WorkSegment(start_time, end_time, is_holiday=False))
                    except ValueError:
                        prefill_data = _build_prefill_from_form(
                            request.form, week_start_date, employee_name, normal_start, normal_end
                        )
                        return render_template(
                            "calculator.html",
                            week_dates=week_dates,
                            employee_name=employee_name,
                            normal_start=normal_start,
                            normal_end=normal_end,
                            prefill_data=prefill_data,
                            error_message=(
                                f"{current_date.isoformat()} 시간 형식이 올바르지 않습니다. HH:MM 형식으로 입력하세요."
                            ),
                        )
                    
                    segment_idx += 1
                
                if segments:
                    ranges = []
                    for seg in segments:
                        start_dt, end_dt = seg.get_datetime_range(current_date)
                        ranges.append((start_dt, end_dt))
                    ranges.sort(key=lambda x: x[0])
                    for idx in range(1, len(ranges)):
                        prev_start, prev_end = ranges[idx - 1]
                        cur_start, _ = ranges[idx]
                        if cur_start < prev_end:
                            prefill_data = _build_prefill_from_form(
                                request.form, week_start_date, employee_name, normal_start, normal_end
                            )
                            return render_template(
                                "calculator.html",
                                week_dates=week_dates,
                                employee_name=employee_name,
                                normal_start=normal_start,
                                normal_end=normal_end,
                                prefill_data=prefill_data,
                                error_message=(
                                    f"{current_date.isoformat()} 근무 시간이 겹칩니다. 겹치지 않게 다시 입력해주세요."
                                ),
                            )

                day_work = DayWork(current_date, segments, is_holiday=is_holiday)
                day_work.memo = day_memo  # 메모 추가
                days.append(day_work)
            
            # 주간 근무 객체 생성
            week_work = WeekWork(week_start_date, days)
            
            # 계산 수행
            result = calculate_week_work(week_work, normal_start, normal_end)
            
            # 주간 집계
            bucket_15_total = sum(day.get("bucket_15_min", 0) for day in result["day_results"])
            bucket_20_total = sum(day.get("bucket_20_min", 0) for day in result["day_results"])
            bucket_25_total = sum(day.get("bucket_25_min", 0) for day in result["day_results"])
            
            # 주말 날짜 계산
            week_end_date = week_start_date + timedelta(days=6)
            next_week_start_dt = datetime.combine(week_end_date + timedelta(days=1), time(0, 0))

            # 자정 이후 이월 시간 계산 (이번 주 집계에서 제외되는 구간)
            carryover_min = 0
            carryover_break_min = 0
            carryover_dates: set[date] = set()
            for day_work in days:
                for seg in day_work.segments:
                    start_dt, end_dt = seg.get_datetime_range(day_work.work_date)
                    if end_dt <= next_week_start_dt:
                        continue
                    carry_start = max(start_dt, next_week_start_dt)
                    if carry_start < end_dt:
                        carryover_min += int((end_dt - carry_start).total_seconds() // 60)
                        carryover_dates.add(day_work.work_date)
            # 이월 구간의 휴게 시간도 제외
            for day_result in result.get("day_results", []):
                day_date_str = day_result.get("date")
                if not day_date_str:
                    continue
                day_date = date.fromisoformat(day_date_str)
                for seg in day_result.get("timeline", []):
                    if seg.get("kind") != "break":
                        continue
                    label = seg.get("label", "")
                    if "~" not in label:
                        continue
                    clean = label.replace("[휴일] ", "").strip()
                    left, right = clean.split("~", 1)
                    left = left.strip()
                    right = right.strip()
                    def _parse_part(part: str) -> Tuple[datetime, datetime]:
                        if " " in part and "/" in part.split(" ", 1)[0]:
                            date_part, time_part = part.split(" ", 1)
                            month_str, day_str = date_part.split("/", 1)
                            hour_str, min_str = time_part.split(":", 1)
                            start = datetime(day_date.year, int(month_str), int(day_str), int(hour_str), int(min_str))
                        else:
                            hour_str, min_str = part.split(":", 1)
                            start = datetime.combine(day_date, time(int(hour_str), int(min_str)))
                        return start, start
                    start_dt, _ = _parse_part(left)
                    end_dt, _ = _parse_part(right)
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    if end_dt <= next_week_start_dt:
                        continue
                    carry_start = max(start_dt, next_week_start_dt)
                    if carry_start < end_dt:
                        carryover_break_min += int((end_dt - carry_start).total_seconds() // 60)
            
            # 메모 및 근무 시간 정보 추가
            for i, day_result in enumerate(result["day_results"]):
                if i < len(days):
                    day_result["memo"] = getattr(days[i], "memo", "")
                    # 근무 시간 세그먼트 정보 추가
                    day_work = days[i]
                    if not day_result.get("is_off", False):
                        segments_info = []
                        work_times_str = ""  # 엑셀 다운로드용 문자열
                        start_times = []
                        end_times = []
                        for seg in day_work.segments:
                            start_str = seg.start_time.strftime("%H:%M")
                            end_str = seg.end_time.strftime("%H:%M")
                            segments_info.append({
                                "start": start_str,
                                "end": end_str
                            })
                            start_times.append(start_str)
                            end_times.append(end_str)
                        day_result["segments"] = segments_info
                        # 엑셀 다운로드용 문자열 형식: "시작1,시작2|종료1,종료2"
                        if start_times and end_times:
                            day_result["work_times_str"] = ",".join(start_times) + "|" + ",".join(end_times)
                        else:
                            day_result["work_times_str"] = ""
                        
                        # 휴게시간 정보 추출 (timeline에서 break 세그먼트 찾기)
                        break_segments = []
                        if "timeline" in day_result:
                            for timeline_seg in day_result["timeline"]:
                                if timeline_seg.get("kind") == "break":
                                    # label에서 시간 추출 (예: "09:00~09:30")
                                    label = timeline_seg.get("label", "")
                                    if "~" in label:
                                        break_segments.append(_format_break_label(label))
                        day_result["break_times"] = break_segments
                    else:
                        day_result["segments"] = []
                        day_result["work_times_str"] = ""
                        day_result["break_times"] = []
            
            weekdays_kr = ['월', '화', '수', '목', '금', '토', '일']
            carryover_date_labels = sorted(
                {f"{d.strftime('%m/%d')}({weekdays_kr[d.weekday()]})" for d in carryover_dates}
            )

            input_data = {
                "employee_name": employee_name,
                "week_start_date": week_start_date.isoformat(),
                "week_end_date": week_end_date.isoformat(),
                "normal_start": normal_start,
                "normal_end": normal_end,
                "carryover_dates_iso": sorted([d.isoformat() for d in carryover_dates]),
                "carryover_min": carryover_min,
                "days": [
                    {
                        "date": d.work_date.isoformat(),
                        "is_off": d.is_off,
                        "is_holiday": d.is_holiday,
                        "memo": getattr(d, "memo", ""),
                        "segments": [
                            {
                                "start": s.start_time.strftime("%H:%M"),
                                "end": s.end_time.strftime("%H:%M"),
                            }
                            for s in d.segments
                        ],
                    }
                    for d in days
                ],
            }
            if carryover_min > 0 and carryover_date_labels:
                input_data["carryover_notice"] = f"{carryover_date_labels[0]} 자정 이후 {carryover_min/60:.1f}h는 다음 주로 자동 이월됩니다."
            result_data = {
                "week_total_min": result["week_total_min"],
                "week_base_min": result.get("week_base_min", 0),
                "week_overtime_min": result.get("week_overtime_min", 0),
                "exceeds_40": result["exceeds_40"],
                "bucket_15_total": bucket_15_total,
                "bucket_20_total": bucket_20_total,
                "bucket_25_total": bucket_25_total,
                "day_results": result["day_results"],
            }
            return render_template(
                "calculator_result.html",
                employee_name=employee_name,
                week_start_date=week_start_date.isoformat(),
                week_end_date=week_end_date.isoformat(),
                weekdays=weekdays,
                week_total_min=result["week_total_min"],
                week_base_min=result.get("week_base_min", 0),
                week_overtime_min=result.get("week_overtime_min", 0),
                exceeds_40=result["exceeds_40"],
                day_results=result["day_results"],
                bucket_15_total=bucket_15_total,
                bucket_20_total=bucket_20_total,
                bucket_25_total=bucket_25_total,
                normal_start=normal_start,
                normal_end=normal_end,
                input_json=json.dumps(input_data, ensure_ascii=False),
                result_json=json.dumps(result_data, ensure_ascii=False),
                carryover_min=carryover_min,
                carryover_date_labels=carryover_date_labels,
                carryover_dates_iso=sorted([d.isoformat() for d in carryover_dates]),
            )
            
        except Exception as e:
            flash(f"계산 중 오류가 발생했습니다: {str(e)}", "danger")
            return redirect(url_for("calculator"))

    # ── 근무일지 라우트 ─────────────────────────────────────────

    @app.route("/worklog")
    def worklog_list():
        logs = get_worklogs()
        employees = get_employees()
        selected_year = request.args.get("year")
        selected_ym   = request.args.get("ym")

        # 연도/월 목록 생성
        years = sorted({l["year"] for l in logs if l["year"]}, reverse=True)
        ym_list = sorted({l["ym"] for l in logs if l["ym"]}, reverse=True)
        year_month_groups: dict = {}
        for ym in ym_list:
            y, m = ym.split("-", 1)
            year_month_groups.setdefault(y, []).append(m)
        for y in year_month_groups:
            year_month_groups[y] = sorted(set(year_month_groups[y]))

        # 필터 적용
        filtered = logs
        if selected_year:
            filtered = [l for l in filtered if l["year"] == selected_year]
        if selected_ym:
            filtered = [l for l in filtered if l["ym"] == selected_ym]

        return render_template("worklog.html",
            logs=filtered,
            employees=employees,
            year_month_groups=year_month_groups,
            selected_year=selected_year,
            selected_ym=selected_ym,
        )

    @app.route("/worklog/add", methods=["POST"])
    def worklog_add():
        client      = request.form.get("client", "").strip()
        description = request.form.get("description", "").strip()
        start_date  = request.form.get("start_date", "").strip()
        start_time  = request.form.get("start_time", "").strip()
        end_date    = request.form.get("end_date", "").strip()
        end_time    = request.form.get("end_time", "").strip()
        workers     = request.form.getlist("workers")
        if not all([client, description, start_date, start_time, end_date, end_time]):
            flash("모든 항목을 입력해주세요.", "danger")
            return redirect(url_for("worklog_list"))
        start_datetime = f"{start_date} {start_time}"
        end_datetime   = f"{end_date} {end_time}"
        add_worklog(client, description, start_datetime, end_datetime, workers)
        flash("근무일지가 등록되었습니다.", "success")
        return redirect(url_for("worklog_list"))

    @app.route("/worklog/<int:worklog_id>/edit", methods=["GET", "POST"])
    def worklog_edit(worklog_id: int):
        log = get_worklog_by_id(worklog_id)
        if not log:
            flash("항목을 찾을 수 없습니다.", "danger")
            return redirect(url_for("worklog_list"))
        employees = get_employees()
        if request.method == "POST":
            client      = request.form.get("client", "").strip()
            description = request.form.get("description", "").strip()
            start_date  = request.form.get("start_date", "").strip()
            start_time  = request.form.get("start_time", "").strip()
            end_date    = request.form.get("end_date", "").strip()
            end_time    = request.form.get("end_time", "").strip()
            workers     = request.form.getlist("workers")
            if not all([client, description, start_date, start_time, end_date, end_time]):
                flash("모든 항목을 입력해주세요.", "danger")
                return render_template("worklog.html",
                    logs=get_worklogs(), employees=employees, edit_log=log,
                    year_month_groups={}, selected_year=None, selected_ym=None)
            start_datetime = f"{start_date} {start_time}"
            end_datetime   = f"{end_date} {end_time}"
            update_worklog(worklog_id, client, description, start_datetime, end_datetime, workers)
            flash("수정되었습니다.", "success")
            return redirect(url_for("worklog_list"))
        logs = get_worklogs()
        years = sorted({l["year"] for l in logs if l["year"]}, reverse=True)
        ym_list = sorted({l["ym"] for l in logs if l["ym"]}, reverse=True)
        year_month_groups: dict = {}
        for ym in ym_list:
            y, m = ym.split("-", 1)
            year_month_groups.setdefault(y, []).append(m)
        return render_template("worklog.html",
            logs=logs, employees=employees, edit_log=log,
            year_month_groups=year_month_groups,
            selected_year=None, selected_ym=None)

    @app.route("/worklog/<int:worklog_id>/delete", methods=["POST"])
    def worklog_delete(worklog_id: int):
        delete_worklog(worklog_id)
        flash("삭제되었습니다.", "success")
        return redirect(url_for("worklog_list"))

    @app.route("/calculator/export", methods=["POST"])
    def calculator_export():
        """계산 결과를 엑셀로 다운로드"""
        try:
            result_json = request.form.get("result_json", "")
            if not result_json:
                flash("엑셀로 변환할 데이터가 없습니다.", "danger")
                return redirect(url_for("calculator"))

            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            from openpyxl.comments import Comment
            from openpyxl.utils import get_column_letter

            result_data = json.loads(result_json)
            employee_name = request.form.get("employee_name", "")
            week_start_date = request.form.get("week_start_date", "")
            week_end_date = request.form.get("week_end_date", "")
            carryover_dates_iso_raw = request.form.get("carryover_dates_iso", "")
            carryover_dates_iso: list[str] = []
            if carryover_dates_iso_raw:
                try:
                    carryover_dates_iso = json.loads(carryover_dates_iso_raw)
                except (TypeError, json.JSONDecodeError):
                    carryover_dates_iso = []
            _apply_display_segments(result_data, carryover_dates_iso, week_end_date)
            week_start_compact = week_start_date.replace("-", "")[2:] if week_start_date else ""
            week_total_min = float(result_data.get("week_total_min", 0))
            week_overtime_min = float(result_data.get("week_overtime_min", 0))
            bucket_15_total = float(result_data.get("bucket_15_total", 0))
            bucket_20_total = float(result_data.get("bucket_20_total", 0))
            bucket_25_total = float(result_data.get("bucket_25_total", 0))
            base_total_min = week_total_min - bucket_15_total - bucket_20_total - bucket_25_total

            wb = Workbook()
            ws = wb.active
            ws.title = "주간 계산"

            header_fill = PatternFill("solid", fgColor="F3F4F6")
            header_font = Font(bold=True)
            align_center = Alignment(horizontal="center", vertical="center")

            col_widths = {}

            def add_row(values, bold=False, fill=False):
                ws.append(values)
                row_idx = ws.max_row
                for col_idx, value in enumerate(values, start=1):
                    text = "" if value is None else str(value)
                    col_widths[col_idx] = max(col_widths.get(col_idx, 0), len(text))
                    cell = ws.cell(row=row_idx, column=col_idx)
                    if bold:
                        cell.font = header_font
                    if fill:
                        cell.fill = header_fill
                    if bold:
                        cell.alignment = align_center

            add_row(["주간 근무 가산수당 계산 결과"], bold=True)
            add_row([f"직원: {employee_name}"])
            add_row([f"기간: {week_start_date} ~ {week_end_date}"])
            add_row([])

            add_row(["주간 집계 요약"], bold=True)
            add_row(["항목", "시간(h)"], bold=True, fill=True)
            add_row(["총 실근로(휴게 제외)", f"{week_total_min/60:.2f}"])
            add_row(["연장근로가 포함된 시간", f"{week_overtime_min/60:.2f}"])
            add_row(["1.0배 시간", f"{base_total_min/60:.2f}"])
            add_row(["1.5배 시간", f"{bucket_15_total/60:.2f}"])
            add_row(["2.0배 시간", f"{bucket_20_total/60:.2f}"])
            add_row(["2.5배 시간", f"{bucket_25_total/60:.2f}"])
            add_row([])

            add_row(["일별 상세 결과"], bold=True)
            add_row([
                "날짜", "근무 상태", "근무 시간", "휴게 시간",
                "총시간(h)", "휴게(h)", "실근로(h)", "1.0배(h)", "1.5배(h)", "2.0배(h)", "2.5배(h)", "메모"
            ], bold=True, fill=True)

            weekdays = ['월', '화', '수', '목', '금', '토', '일']

            overtime_rows = []
            for idx, day in enumerate(result_data.get("day_results", [])):
                is_holiday = day.get("is_holiday", False)
                is_off = day.get("is_off", False)
                weekday = weekdays[idx] if idx < len(weekdays) else ""
                date_label = f"{day.get('date', '')}({weekday})" if weekday else day.get("date", "")
                status_parts = []
                if is_holiday:
                    status_parts.append("휴일")
                if is_off:
                    status_parts.append("근무안함")
                status = ", ".join(status_parts) if status_parts else "근무"

                if is_off:
                    add_row([date_label, status, "-", "-", "-", "-", "-", "-", "-", "-", "-", day.get("memo", "")])
                    continue

                segments = day.get("display_segments") or day.get("segments", [])
                work_times = ", ".join(
                    f"{seg.get('start')}~{seg.get('end')}"
                    for seg in segments
                    if seg.get("start") and seg.get("end")
                ) or "-"
                break_times = ", ".join(
                    _format_break_label(t or "") for t in day.get("break_times", [])
                ) or "-"

                total_h = (day.get("work_min", 0) + day.get("break_min", 0)) / 60
                break_h = day.get("break_min", 0) / 60
                work_h = day.get("work_min", 0) / 60
                base_h = (day.get("work_min", 0) - day.get("bucket_15_min", 0)
                          - day.get("bucket_20_min", 0) - day.get("bucket_25_min", 0)) / 60
                calc_by_kind = {"m15": [], "m20": [], "m25": []}
                for seg in day.get("timeline", []):
                    if seg.get("kind") == "break":
                        continue
                    calc = seg.get("calculation")
                    if calc:
                        calc_text = calc.replace("기본 1.0배", "").replace("\n", " / ").strip(" /")
                        kind = seg.get("kind")
                        if kind in calc_by_kind:
                            calc_by_kind[kind].append(f"{seg.get('label', '')}: {calc_text}")

                add_row([
                    date_label,
                    status,
                    work_times,
                    break_times,
                    f"{total_h:.2f}",
                    f"{break_h:.2f}",
                    f"{work_h:.2f}",
                    f"{base_h:.2f}",
                    f"{day.get('bucket_15_min', 0) / 60:.2f}",
                    f"{day.get('bucket_20_min', 0) / 60:.2f}",
                    f"{day.get('bucket_25_min', 0) / 60:.2f}",
                    day.get("memo", ""),
                ])
                if (
                    day.get("bucket_15_min", 0) > 0
                    or day.get("bucket_20_min", 0) > 0
                    or day.get("bucket_25_min", 0) > 0
                ):
                    overtime_rows.append(
                        [
                            date_label,
                            f"{day.get('bucket_15_min', 0) / 60:.2f}",
                            f"{day.get('bucket_20_min', 0) / 60:.2f}",
                            f"{day.get('bucket_25_min', 0) / 60:.2f}",
                            f"{work_times} / {day.get('memo', '')}".strip(" /"),
                        ]
                    )

                row_idx = ws.max_row
                for col_idx, kind_key, minute_key in [
                    (9, "m15", "bucket_15_min"),
                    (10, "m20", "bucket_20_min"),
                    (11, "m25", "bucket_25_min"),
                ]:
                    minutes = day.get(minute_key, 0)
                    if minutes and calc_by_kind[kind_key]:
                        comment_text = "\n".join(calc_by_kind[kind_key])
                        ws.cell(row=row_idx, column=col_idx).comment = Comment(comment_text, "WorkPay")

            for col_idx, width in col_widths.items():
                ws.column_dimensions[get_column_letter(col_idx)].width = min(width + 2, 60)

            if overtime_rows:
                add_row([])
                add_row([f"연장근무확인서 ({employee_name}_{week_start_compact})"], bold=True)
                add_row(["날짜", "연장근무1.5", "연장근무2.0", "연장근무2.5", "적요"], bold=True, fill=True)
                for row in overtime_rows:
                    add_row(row)

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            response = make_response(output.read())
            response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            from urllib.parse import quote
            filename_display = f"주간 근무 가산수당 계산 결과_{employee_name}({week_start_date} ~ {week_end_date}).xlsx"
            filename_ascii = f"workpay_{week_start_date}_{week_end_date}.xlsx"
            response.headers["Content-Disposition"] = (
                f"attachment; filename=\"{filename_ascii}\"; "
                f"filename*=UTF-8''{quote(filename_display)}"
            )
            return response

            # POST 데이터에서 결과 정보 가져오기
            employee_name = request.form.get("employee_name", "")
            week_start_date = request.form.get("week_start_date")
            week_end_date = request.form.get("week_end_date")
            week_total_min = float(request.form.get("week_total_min", 0))
            week_overtime_min = float(request.form.get("week_overtime_min", 0))
            bucket_15_total = float(request.form.get("bucket_15_total", 0))
            bucket_20_total = float(request.form.get("bucket_20_total", 0))
            bucket_25_total = float(request.form.get("bucket_25_total", 0))
            
            # CSV 생성 (엑셀에서 열 수 있음, UTF-8-sig BOM 포함)
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 헤더
            writer.writerow(["주간 근무 가산수당 계산 결과"])
            writer.writerow([f"직원: {employee_name}"])
            writer.writerow([f"기간: {week_start_date} ~ {week_end_date}"])
            writer.writerow([])
            
            # 요약
            writer.writerow(["주간 집계 요약"])
            writer.writerow(["항목", "시간(h)"])
            base_total_min = week_total_min - bucket_15_total - bucket_20_total - bucket_25_total
            writer.writerow(["총 실근로", f"{week_total_min/60:.2f}"])
            writer.writerow(["연장근로가 포함된 시간", f"{week_overtime_min/60:.2f}"])
            writer.writerow(["1.0배 시간", f"{base_total_min/60:.2f}"])
            writer.writerow(["1.5배 시간", f"{bucket_15_total/60:.2f}"])
            writer.writerow(["2.0배 시간", f"{bucket_20_total/60:.2f}"])
            writer.writerow(["2.5배 시간", f"{bucket_25_total/60:.2f}"])
            writer.writerow([])
            
            # 일별 상세
            writer.writerow(["일별 상세 결과"])
            writer.writerow(["요일", "날짜", "근무 시간", "총시간(h)", "휴게(h)", "실근로(h)", "1.0배(h)", "1.5배(h)", "2.0배(h)", "2.5배(h)", "메모"])
            
            weekdays = ['월', '화', '수', '목', '금', '토', '일']
            day_idx = 0
            
            while True:
                date_key = f"day_date_{day_idx}"
                if date_key not in request.form:
                    break
                
                day_date = request.form.get(date_key)
                is_off = request.form.get(f"day_off_{day_idx}") == "true"
                work_min = float(request.form.get(f"day_work_min_{day_idx}", 0))
                break_min = float(request.form.get(f"day_break_min_{day_idx}", 0))
                bucket_15 = float(request.form.get(f"day_bucket_15_{day_idx}", 0))
                bucket_20 = float(request.form.get(f"day_bucket_20_{day_idx}", 0))
                bucket_25 = float(request.form.get(f"day_bucket_25_{day_idx}", 0))
                memo = request.form.get(f"day_memo_{day_idx}", "")
                
                # 근무 시간 정보 파싱
                work_times_str = request.form.get(f"day_work_times_{day_idx}", "")
                work_times_display = "-"
                if work_times_str and work_times_str.strip() and not is_off:
                    try:
                        # 형식: "시작1,시작2|종료1,종료2"
                        if "|" in work_times_str:
                            start_times_str, end_times_str = work_times_str.split("|", 1)
                            start_times = [t.strip() for t in start_times_str.split(",") if t.strip()]
                            end_times = [t.strip() for t in end_times_str.split(",") if t.strip()]
                            
                            # 각 시간대를 "시작~종료" 형식으로 조합
                            time_pairs = []
                            max_len = max(len(start_times), len(end_times))
                            for i in range(max_len):
                                start = start_times[i] if i < len(start_times) else ""
                                end = end_times[i] if i < len(end_times) else ""
                                if start and end:
                                    time_pairs.append(f"{start}~{end}")
                            
                            if time_pairs:
                                work_times_display = ", ".join(time_pairs)
                            else:
                                work_times_display = "-"
                        else:
                            work_times_display = "-"
                    except Exception as e:
                        # 디버깅을 위해 에러는 무시하되 기본값 사용
                        work_times_display = "-"
                
                weekday = weekdays[day_idx] if day_idx < len(weekdays) else ""
                
                if is_off:
                    writer.writerow([weekday, day_date, "-", "-", "-", "-", "-", "-", "-", "-", memo])
                else:
                    base_min = work_min - bucket_15 - bucket_20 - bucket_25
                    writer.writerow([
                        weekday,
                        day_date,
                        work_times_display,
                        f"{(work_min + break_min)/60:.2f}",
                        f"{break_min/60:.2f}",
                        f"{work_min/60:.2f}",
                        f"{base_min/60:.2f}",
                        f"{bucket_15/60:.2f}",
                        f"{bucket_20/60:.2f}",
                        f"{bucket_25/60:.2f}",
                        memo
                    ])
                
                day_idx += 1
            
            # UTF-8-sig BOM 추가하여 한글 깨짐 방지
            csv_content = output.getvalue()
            # BOM 추가하고 UTF-8-sig로 인코딩
            csv_bytes = ('\ufeff' + csv_content).encode('utf-8-sig')
            
            # 응답 생성
            response = make_response(csv_bytes)
            response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
            filename_display = f"주간 근무 가산수당 계산 결과_{employee_name}({week_start_date} ~ {week_end_date}).csv"
            filename_ascii = f"workpay_{week_start_date}_{week_end_date}.csv"
            response.headers["Content-Disposition"] = (
                f"attachment; filename=\"{filename_ascii}\"; "
                f"filename*=UTF-8''{quote(filename_display)}"
            )
            
            return response
            
        except Exception as e:
            flash(f"엑셀 다운로드 중 오류가 발생했습니다: {str(e)}", "danger")
            return redirect(url_for("calculator"))


    @app.route("/calculator/save", methods=["POST"])
    def calculator_save():
        try:
            employee_name = (request.form.get("employee_name") or "").strip()
            if not employee_name:
                flash("직원을 선택하세요.", "danger")
                return redirect(url_for("employees"))

            week_start_date = request.form.get("week_start_date")
            week_end_date = request.form.get("week_end_date")
            normal_start = request.form.get("normal_start")
            normal_end = request.form.get("normal_end")
            input_json = request.form.get("input_json")
            result_json = request.form.get("result_json")

            if not all([week_start_date, week_end_date, normal_start, normal_end, input_json, result_json]):
                flash("저장할 데이터가 부족합니다.", "danger")
                return redirect(url_for("employee_detail", employee_name=employee_name))

            result_data = json.loads(result_json)
            needs_review = (
                result_data.get("week_total_min", 0) > 52 * 60
                or result_data.get("week_overtime_min", 0) > 12 * 60
            )
            save_weekly_calculation(
                employee_name=employee_name,
                week_start_date=week_start_date,
                week_end_date=week_end_date,
                normal_start=normal_start,
                normal_end=normal_end,
                input_json=input_json,
                result_json=result_json,
                needs_review=needs_review,
            )

            # 자정 이후 이월 시간 자동 저장 (다음 주 미리 저장)
            input_data = json.loads(input_json)
            result_data = json.loads(result_json)
            base_week_end = date.fromisoformat(week_end_date)
            next_week_start_date = base_week_end + timedelta(days=1)
            next_week_end_date = next_week_start_date + timedelta(days=6)
            next_week_start_dt = datetime.combine(next_week_start_date, time(0, 0))
            next_week_end_dt = next_week_start_dt + timedelta(days=7)

            next_week_segments_by_date: dict[date, list[dict]] = {}
            carryover_memos_by_date: dict[date, list[str]] = {}
            for day in input_data.get("days", []):
                day_date_str = day.get("date")
                if not day_date_str:
                    continue
                day_date = date.fromisoformat(day_date_str)
                day_memo = (day.get("memo") or "").strip()
                for seg in day.get("segments", []):
                    start_str = seg.get("start")
                    end_str = seg.get("end")
                    if not start_str or not end_str:
                        continue
                    start_dt = datetime.combine(day_date, datetime.strptime(start_str, "%H:%M").time())
                    end_dt = datetime.combine(day_date, datetime.strptime(end_str, "%H:%M").time())
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)

                    if end_dt <= next_week_start_dt:
                        continue
                    carry_start = max(start_dt, next_week_start_dt)
                    carry_end = min(end_dt, next_week_end_dt)
                    if carry_start >= carry_end:
                        continue

                    current_start = carry_start
                    while current_start < carry_end:
                        current_date = current_start.date()
                        day_end_dt = datetime.combine(current_date, time(0, 0)) + timedelta(days=1)
                        segment_end = min(carry_end, day_end_dt)

                        if current_date not in next_week_segments_by_date:
                            next_week_segments_by_date[current_date] = []
                        next_week_segments_by_date[current_date].append(
                            {
                                "start": current_start.strftime("%H:%M"),
                                "end": segment_end.strftime("%H:%M"),
                            }
                        )
                        if day_memo:
                            memo_list = carryover_memos_by_date.setdefault(current_date, [])
                            if day_memo not in memo_list:
                                memo_list.append(day_memo)
                        current_start = segment_end

            def parse_timeline_label(base_date: date, label: str) -> Optional[Tuple[datetime, datetime]]:
                clean_label = label.replace("[휴일] ", "").strip()
                if "~" not in clean_label:
                    return None
                left, right = clean_label.split("~", 1)
                left = left.strip()
                right = right.strip()

                def parse_part(part: str) -> Tuple[Optional[int], Optional[int], int, int]:
                    if "/" in part:
                        date_part, time_part = part.split(" ", 1)
                        month_str, day_str = date_part.split("/", 1)
                        hour_str, min_str = time_part.split(":", 1)
                        return int(month_str), int(day_str), int(hour_str), int(min_str)
                    hour_str, min_str = part.split(":", 1)
                    return None, None, int(hour_str), int(min_str)

                l_month, l_day, l_hour, l_min = parse_part(left)
                r_month, r_day, r_hour, r_min = parse_part(right)

                if l_month is None:
                    start_dt = datetime.combine(base_date, time(l_hour, l_min))
                else:
                    start_dt = datetime(base_date.year, l_month, l_day, l_hour, l_min)

                if r_month is None:
                    end_dt = datetime.combine(start_dt.date(), time(r_hour, r_min))
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                else:
                    end_year = base_date.year
                    if r_month < (l_month or start_dt.month):
                        end_year += 1
                    end_dt = datetime(end_year, r_month, r_day, r_hour, r_min)

                return start_dt, end_dt

            carryover_override_by_date: dict[date, list[dict]] = {}
            for day in result_data.get("day_results", []):
                day_date_str = day.get("date")
                if not day_date_str:
                    continue
                day_date = date.fromisoformat(day_date_str)
                for seg in day.get("timeline", []):
                    label = seg.get("label", "")
                    parsed = parse_timeline_label(day_date, label)
                    if not parsed:
                        continue
                    start_dt, end_dt = parsed
                    if end_dt <= next_week_start_dt or start_dt >= next_week_end_dt:
                        continue
                    carry_start = max(start_dt, next_week_start_dt)
                    carry_end = min(end_dt, next_week_end_dt)
                    if carry_start >= carry_end:
                        continue
                    effective_kind = seg.get("original_kind") or seg.get("kind", "base")
                    if effective_kind == "carry":
                        effective_kind = "base"
                    effective_calc = seg.get("original_calculation") or seg.get("calculation", "")

                    current_start = carry_start
                    while current_start < carry_end:
                        current_date = current_start.date()
                        day_end_dt = datetime.combine(current_date, time(0, 0)) + timedelta(days=1)
                        segment_end = min(carry_end, day_end_dt)
                        if current_date not in carryover_override_by_date:
                            carryover_override_by_date[current_date] = []
                        carryover_override_by_date[current_date].append(
                            {
                                "start_dt": current_start,
                                "end_dt": segment_end,
                                "kind": effective_kind,
                                "calculation": effective_calc,
                                "holiday_label": label.startswith("[휴일] "),
                            }
                        )
                        current_start = segment_end

            if next_week_segments_by_date:
                next_week_days: list[DayWork] = []
                next_week_input_days: list[dict] = []
                for i in range(7):
                    current_date = next_week_start_date + timedelta(days=i)
                    segs = next_week_segments_by_date.get(current_date, [])
                    work_segments = [WorkSegment(s["start"], s["end"], is_holiday=False) for s in segs]
                    day_work = DayWork(current_date, work_segments, is_holiday=False)
                    memo_list = carryover_memos_by_date.get(current_date, [])
                    memo_text = " / ".join(memo_list)
                    if memo_text:
                        day_work.memo = memo_text
                    next_week_days.append(day_work)
                    next_week_input_days.append(
                        {
                            "date": current_date.isoformat(),
                            "is_off": day_work.is_off,
                            "is_holiday": False,
                            "memo": memo_text,
                            "segments": [{"start": s["start"], "end": s["end"]} for s in segs],
                        }
                    )

                next_week_work = WeekWork(next_week_start_date, next_week_days)
                next_week_result = calculate_week_work(next_week_work, normal_start, normal_end)

                # 자동 이월 결과에도 근무 시간/휴게 정보 추가
                for i, day_result in enumerate(next_week_result.get("day_results", [])):
                    if i < len(next_week_days):
                        day_work = next_week_days[i]
                        if not day_result.get("is_off", False):
                            segments_info = []
                            work_times_str = ""
                            start_times = []
                            end_times = []
                            for seg in day_work.segments:
                                start_str = seg.start_time.strftime("%H:%M")
                                end_str = seg.end_time.strftime("%H:%M")
                                segments_info.append({"start": start_str, "end": end_str})
                                start_times.append(start_str)
                                end_times.append(end_str)
                            day_result["segments"] = segments_info
                            if start_times and end_times:
                                day_result["work_times_str"] = ",".join(start_times) + "|" + ",".join(end_times)
                            else:
                                day_result["work_times_str"] = ""

                            break_segments = []
                            if "timeline" in day_result:
                                for timeline_seg in day_result["timeline"]:
                                    if timeline_seg.get("kind") == "break":
                                        label = timeline_seg.get("label", "")
                                        if "~" in label:
                                            break_segments.append(_format_break_label(label))
                            day_result["break_times"] = break_segments
                        else:
                            day_result["segments"] = []
                            day_result["work_times_str"] = ""
                            day_result["break_times"] = []

                # 이월된 구간은 이전 주 ERP 집계 결과 기준으로 타임라인/집계 덮어쓰기
                if carryover_override_by_date:
                    for day_result in next_week_result.get("day_results", []):
                        day_date_str = day_result.get("date")
                        if not day_date_str:
                            continue
                        day_date = date.fromisoformat(day_date_str)
                        if day_date not in carryover_override_by_date:
                            continue

                        segments = carryover_override_by_date[day_date]
                        work_min = 0
                        break_min = 0
                        overtime_min = 0
                        bucket_15 = 0
                        bucket_20 = 0
                        bucket_25 = 0
                        base_min = 0
                        timeline_segments = []
                        max_end_minutes = 0
                        base_dt = datetime.combine(day_date, time(0, 0))

                        for seg in segments:
                            start_dt = seg["start_dt"]
                            end_dt = seg["end_dt"]
                            kind = seg["kind"]
                            calculation = seg.get("calculation", "")
                            holiday_label = seg.get("holiday_label", False)
                            duration_min = int((end_dt - start_dt).total_seconds() // 60)
                            start_minutes = int((start_dt - base_dt).total_seconds() // 60)
                            end_minutes = start_minutes + duration_min
                            max_end_minutes = max(max_end_minutes, end_minutes)

                            if kind == "break":
                                break_min += duration_min
                            else:
                                work_min += duration_min
                                if "연장근로" in (calculation or ""):
                                    overtime_min += duration_min
                                if kind == "m15":
                                    bucket_15 += duration_min
                                elif kind == "m20":
                                    bucket_20 += duration_min
                                elif kind == "m25":
                                    bucket_25 += duration_min
                                elif kind == "base":
                                    base_min += duration_min

                            label = (
                                f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
                                if start_dt.date() == end_dt.date()
                                else f"{start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%m/%d %H:%M')}"
                            )
                            if holiday_label:
                                label = f"[휴일] {label}"
                            timeline_segments.append(
                                {
                                    "start_minutes": start_minutes,
                                    "duration_min": duration_min,
                                    "kind": kind,
                                    "label": label,
                                    "calculation": calculation,
                                }
                            )

                        if max_end_minutes > 1440:
                            max_timeline_minutes = ((max_end_minutes - 1) // 360 + 1) * 360
                            max_timeline_minutes = min(max_timeline_minutes, 2880)
                        else:
                            max_timeline_minutes = 1440

                        for seg in timeline_segments:
                            seg["left"] = round((seg["start_minutes"] / max_timeline_minutes) * 100, 4)
                            seg["width"] = round((seg["duration_min"] / max_timeline_minutes) * 100, 4)
                            del seg["start_minutes"]
                            del seg["duration_min"]

                        day_result["work_min"] = work_min
                        day_result["break_min"] = break_min
                        day_result["overtime_min"] = overtime_min
                        day_result["bucket_15_min"] = bucket_15
                        day_result["bucket_20_min"] = bucket_20
                        day_result["bucket_25_min"] = bucket_25
                        day_result["timeline"] = timeline_segments
                        day_result["max_timeline_hours"] = max_timeline_minutes // 60
                        day_result["has_admin_interpretation"] = False
                        day_result["break_times"] = [
                            _format_break_label(seg["label"]) for seg in timeline_segments
                            if seg.get("kind") == "break" and "~" in seg.get("label", "")
                        ]

                next_week_bucket_15 = sum(day.get("bucket_15_min", 0) for day in next_week_result["day_results"])
                next_week_bucket_20 = sum(day.get("bucket_20_min", 0) for day in next_week_result["day_results"])
                next_week_bucket_25 = sum(day.get("bucket_25_min", 0) for day in next_week_result["day_results"])
                next_week_total_min = sum(day.get("work_min", 0) for day in next_week_result["day_results"])
                next_week_overtime_min = sum(day.get("overtime_min", 0) for day in next_week_result["day_results"])
                next_week_base_min = sum(
                    min(
                        max(
                            0,
                            day.get("work_min", 0)
                            - day.get("bucket_15_min", 0)
                            - day.get("bucket_20_min", 0)
                            - day.get("bucket_25_min", 0),
                        ),
                        DAY_LIMIT_MIN,
                    )
                    for day in next_week_result["day_results"]
                )
                next_week_exceeds_40 = next_week_total_min > WEEK_LIMIT_40_MIN

                next_week_input = {
                    "employee_name": employee_name,
                    "week_start_date": next_week_start_date.isoformat(),
                    "week_end_date": next_week_end_date.isoformat(),
                    "normal_start": normal_start,
                    "normal_end": normal_end,
                    "auto_carryover": True,
                    "carryover_from": week_start_date,
                    "days": next_week_input_days,
                }
                next_week_result_payload = {
                    "week_total_min": next_week_total_min,
                    "week_base_min": next_week_base_min,
                    "exceeds_40": next_week_exceeds_40,
                    "bucket_15_total": next_week_bucket_15,
                    "bucket_20_total": next_week_bucket_20,
                    "bucket_25_total": next_week_bucket_25,
                    "week_overtime_min": next_week_overtime_min,
                    "day_results": next_week_result["day_results"],
                }

                needs_review_next = (
                    next_week_result_payload.get("week_total_min", 0) > 52 * 60
                    or next_week_result_payload.get("week_overtime_min", 0) > 12 * 60
                )
                save_weekly_calculation(
                    employee_name=employee_name,
                    week_start_date=next_week_start_date.isoformat(),
                    week_end_date=next_week_end_date.isoformat(),
                    normal_start=normal_start,
                    normal_end=normal_end,
                    input_json=json.dumps(next_week_input, ensure_ascii=False),
                    result_json=json.dumps(next_week_result_payload, ensure_ascii=False),
                    needs_review=needs_review_next,
                )

            flash("내역이 저장되었습니다.", "success")
            return redirect(url_for("employee_detail", employee_name=employee_name))
        except Exception as e:
            flash(f"저장 중 오류가 발생했습니다: {str(e)}", "danger")
            return redirect(url_for("employees"))
