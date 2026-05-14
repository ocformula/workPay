import sqlite3
from typing import List, Optional

from config import DB_PATH, DEFAULT_EMPLOYEES


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deleted_weekly_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                employee_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                needs_review INTEGER NOT NULL DEFAULT 0,
                week_start_date TEXT NOT NULL,
                week_end_date TEXT NOT NULL,
                normal_start TEXT NOT NULL,
                normal_end TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                deleted_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                needs_review INTEGER NOT NULL DEFAULT 0,
                week_start_date TEXT NOT NULL,
                week_end_date TEXT NOT NULL,
                normal_start TEXT NOT NULL,
                normal_end TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worklog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client TEXT NOT NULL,
                description TEXT NOT NULL,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worklog_workers (
                worklog_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                PRIMARY KEY (worklog_id, employee_name),
                FOREIGN KEY (worklog_id) REFERENCES worklog(id)
            );
            """
        )
        # 기존 컬럼이 있는 DB 마이그레이션 (구버전 호환)
        _ensure_column(conn, "worklog", "start_datetime", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "worklog", "end_datetime",   "TEXT NOT NULL DEFAULT ''")
        # 구버전 DB의 work_date NOT NULL 제약을 우회 — SQLite는 컬럼 제약 변경 불가이므로
        # INSERT 시 work_date 컬럼이 존재하면 빈 문자열 기본값 컬럼으로 간주하고 무시
        # (새 DB는 work_date 컬럼 없음, 구 DB는 아래 _patch로 대응)
        _patch_worklog_work_date(conn)
        _ensure_column(conn, "weekly_calculations", "needs_review", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "deleted_weekly_calculations", "needs_review", "INTEGER NOT NULL DEFAULT 0")
        for name in DEFAULT_EMPLOYEES:
            conn.execute(
                "INSERT OR IGNORE INTO employees (name) VALUES (?);",
                (name,),
            )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table});").fetchall()
    existing = {row["name"] for row in cols}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl};")


def _patch_worklog_work_date(conn: sqlite3.Connection) -> None:
    """구버전 DB의 work_date NOT NULL 컬럼을 start_datetime 값으로 채워 제약 위반 방지"""
    cols = conn.execute("PRAGMA table_info(worklog);").fetchall()
    col_names = {row["name"] for row in cols}
    if "work_date" not in col_names:
        return
    # start_datetime이 있는 행 중 work_date가 비어있으면 채움
    conn.execute("""
        UPDATE worklog
        SET work_date = substr(start_datetime, 1, 10)
        WHERE (work_date IS NULL OR work_date = '')
          AND start_datetime != '';
    """)


def get_employees() -> List[str]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT name FROM employees ORDER BY name;").fetchall()
    return [row[0] for row in rows]


def get_employee_id(name: str) -> Optional[int]:
    with _get_conn() as conn:
        row = conn.execute("SELECT id FROM employees WHERE name = ?;", (name,)).fetchone()
        return row[0] if row else None


def get_employee_overview() -> List[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT e.name AS name,
                   COUNT(w.id) AS calc_count,
                   MAX(w.week_start_date) AS latest_week_start
            FROM employees e
            LEFT JOIN weekly_calculations w ON w.employee_id = e.id
            GROUP BY e.id
            ORDER BY e.name;
            """
        ).fetchall()
    return [
        {
            "name": row["name"],
            "calc_count": row["calc_count"],
            "latest_ym": row["latest_week_start"][:7] if row["latest_week_start"] else None,
        }
        for row in rows
    ]



def add_employee(name: str) -> None:
    clean = (name or "").strip()
    if not clean:
        return
    with _get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO employees (name) VALUES (?);", (clean,))


def get_employee_admin_list() -> List[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT e.id AS id,
                   e.name AS name,
                   (SELECT COUNT(*) FROM weekly_calculations w WHERE w.employee_id = e.id) AS calc_count,
                   (SELECT COUNT(*) FROM deleted_weekly_calculations d WHERE d.employee_id = e.id) AS trash_count
            FROM employees e
            ORDER BY e.name;
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "calc_count": row["calc_count"],
            "trash_count": row["trash_count"],
        }
        for row in rows
    ]


def get_employee_usage_counts(employee_id: int) -> tuple[int, int]:
    with _get_conn() as conn:
        calc_count = conn.execute(
            "SELECT COUNT(*) FROM weekly_calculations WHERE employee_id = ?;",
            (employee_id,),
        ).fetchone()[0]
        trash_count = conn.execute(
            "SELECT COUNT(*) FROM deleted_weekly_calculations WHERE employee_id = ?;",
            (employee_id,),
        ).fetchone()[0]
    return int(calc_count), int(trash_count)


def delete_employee_by_id(employee_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM employees WHERE id = ?;", (employee_id,))


def get_employee_calculations(employee_name: str) -> List[sqlite3.Row]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.*
            FROM weekly_calculations w
            JOIN employees e ON e.id = w.employee_id
            WHERE e.name = ?
            ORDER BY w.week_start_date DESC, w.created_at DESC;
            """,
            (employee_name,),
        ).fetchall()
    return rows


def get_calculation_by_id(calc_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT w.*, e.name AS employee_name
            FROM weekly_calculations w
            JOIN employees e ON e.id = w.employee_id
            WHERE w.id = ?;
            """,
            (calc_id,),
        ).fetchone()
    return row


def delete_calculation_by_id(calc_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM weekly_calculations WHERE id = ?;", (calc_id,))


def move_calculation_to_trash(calc_id: int) -> None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT w.*, e.name AS employee_name
            FROM weekly_calculations w
            JOIN employees e ON e.id = w.employee_id
            WHERE w.id = ?;
            """,
            (calc_id,),
        ).fetchone()
        if not row:
            return
        conn.execute(
            """
            INSERT INTO deleted_weekly_calculations
            (original_id, employee_id, employee_name, needs_review, week_start_date, week_end_date,
             normal_start, normal_end, input_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                row["id"],
                row["employee_id"],
                row["employee_name"],
                row["needs_review"] if "needs_review" in row.keys() else 0,
                row["week_start_date"],
                row["week_end_date"],
                row["normal_start"],
                row["normal_end"],
                row["input_json"],
                row["result_json"],
                row["created_at"],
            ),
        )
        conn.execute("DELETE FROM weekly_calculations WHERE id = ?;", (calc_id,))


def get_deleted_calculations() -> List[sqlite3.Row]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM deleted_weekly_calculations
            ORDER BY deleted_at DESC;
            """
        ).fetchall()
    return rows


def get_deleted_calculation_by_id(trash_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM deleted_weekly_calculations WHERE id = ?;",
            (trash_id,),
        ).fetchone()
    return row


def restore_deleted_calculation(trash_id: int) -> None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM deleted_weekly_calculations WHERE id = ?;",
            (trash_id,),
        ).fetchone()
        if not row:
            return
        conn.execute(
            "INSERT OR IGNORE INTO employees (name) VALUES (?);",
            (row["employee_name"],),
        )
        employee_id = conn.execute(
            "SELECT id FROM employees WHERE name = ?;",
            (row["employee_name"],),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO weekly_calculations
            (employee_id, needs_review, week_start_date, week_end_date, normal_start, normal_end, input_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                employee_id,
                row["needs_review"] if "needs_review" in row.keys() else 0,
                row["week_start_date"],
                row["week_end_date"],
                row["normal_start"],
                row["normal_end"],
                row["input_json"],
                row["result_json"],
            ),
        )
        conn.execute("DELETE FROM deleted_weekly_calculations WHERE id = ?;", (trash_id,))


def purge_deleted_calculation(trash_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM deleted_weekly_calculations WHERE id = ?;", (trash_id,))


def save_weekly_calculation(
    employee_name: str,
    week_start_date: str,
    week_end_date: str,
    normal_start: str,
    normal_end: str,
    input_json: str,
    result_json: str,
    needs_review: bool = False,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO employees (name) VALUES (?);",
            (employee_name,),
        )
        employee_id = conn.execute(
            "SELECT id FROM employees WHERE name = ?;",
            (employee_name,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO weekly_calculations
            (employee_id, needs_review, week_start_date, week_end_date, normal_start, normal_end, input_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                employee_id,
                1 if needs_review else 0,
                week_start_date,
                week_end_date,
                normal_start,
                normal_end,
                input_json,
                result_json,
            ),
        )


# ── 근무일지 CRUD ──────────────────────────────────────────────

def get_worklogs() -> List[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.*, GROUP_CONCAT(ww.employee_name, ',') AS workers
            FROM worklog w
            LEFT JOIN worklog_workers ww ON ww.worklog_id = w.id
            GROUP BY w.id
            ORDER BY w.start_datetime DESC;
            """
        ).fetchall()
    result = []
    for row in rows:
        start_dt = row["start_datetime"] or ""
        result.append({
            "id": row["id"],
            "client": row["client"],
            "description": row["description"],
            "start_datetime": start_dt,
            "end_datetime": row["end_datetime"] or "",
            "start_date": start_dt[:10] if start_dt else "",
            "ym": start_dt[:7] if start_dt else "",
            "year": start_dt[:4] if start_dt else "",
            "created_at": row["created_at"],
            "workers": row["workers"].split(",") if row["workers"] else [],
        })
    return result


def get_worklog_by_id(worklog_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM worklog WHERE id = ?;", (worklog_id,)
        ).fetchone()
        if not row:
            return None
        workers = conn.execute(
            "SELECT employee_name FROM worklog_workers WHERE worklog_id = ?;",
            (worklog_id,),
        ).fetchall()
    start_dt = row["start_datetime"] or ""
    return {
        "id": row["id"],
        "client": row["client"],
        "description": row["description"],
        "start_datetime": start_dt,
        "end_datetime": row["end_datetime"] or "",
        "start_date": start_dt[:10] if start_dt else "",
        "ym": start_dt[:7] if start_dt else "",
        "year": start_dt[:4] if start_dt else "",
        "created_at": row["created_at"],
        "workers": [w["employee_name"] for w in workers],
    }


def add_worklog(client: str, description: str,
                start_datetime: str, end_datetime: str,
                workers: List[str]) -> int:
    with _get_conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(worklog);").fetchall()}
        fields = ["client", "description", "start_datetime", "end_datetime"]
        values: list = [client, description, start_datetime, end_datetime]
        if "work_date" in cols:
            fields.append("work_date")
            values.append(start_datetime[:10])
        if "start_time" in cols:
            fields.append("start_time")
            values.append(start_datetime[11:])
        if "end_time" in cols:
            fields.append("end_time")
            values.append(end_datetime[11:])
        placeholders = ", ".join("?" * len(fields))
        col_names = ", ".join(fields)
        cur = conn.execute(
            f"INSERT INTO worklog ({col_names}) VALUES ({placeholders});",
            values,
        )
        worklog_id = cur.lastrowid
        for name in workers:
            conn.execute(
                "INSERT OR IGNORE INTO worklog_workers (worklog_id, employee_name) VALUES (?, ?);",
                (worklog_id, name),
            )
    return worklog_id


def update_worklog(worklog_id: int, client: str, description: str,
                   start_datetime: str, end_datetime: str,
                   workers: List[str]) -> None:
    with _get_conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(worklog);").fetchall()}
        sets = ["client=?", "description=?", "start_datetime=?", "end_datetime=?"]
        values: list = [client, description, start_datetime, end_datetime]
        if "work_date" in cols:
            sets.append("work_date=?")
            values.append(start_datetime[:10])
        if "start_time" in cols:
            sets.append("start_time=?")
            values.append(start_datetime[11:])
        if "end_time" in cols:
            sets.append("end_time=?")
            values.append(end_datetime[11:])
        values.append(worklog_id)
        conn.execute(
            f"UPDATE worklog SET {', '.join(sets)} WHERE id=?;",
            values,
        )
        conn.execute("DELETE FROM worklog_workers WHERE worklog_id=?;", (worklog_id,))
        for name in workers:
            conn.execute(
                "INSERT OR IGNORE INTO worklog_workers (worklog_id, employee_name) VALUES (?, ?);",
                (worklog_id, name),
            )


def delete_worklog(worklog_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM worklog_workers WHERE worklog_id=?;", (worklog_id,))
        conn.execute("DELETE FROM worklog WHERE id=?;", (worklog_id,))
