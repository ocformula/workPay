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
            SELECT e.name AS name, COUNT(w.id) AS calc_count
            FROM employees e
            LEFT JOIN weekly_calculations w ON w.employee_id = e.id
            GROUP BY e.id
            ORDER BY e.name;
            """
        ).fetchall()
    return [{"name": row["name"], "calc_count": row["calc_count"]} for row in rows]



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
