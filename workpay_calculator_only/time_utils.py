from datetime import datetime, date, time, timedelta
from typing import Tuple

from config import WEEK_START_ISO


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_time(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


def dt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def dt_from_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def minutes_between(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def week_start(d: date) -> date:
    # ISO: Monday=0 .. Sunday=6
    delta = (d.weekday() - WEEK_START_ISO) % 7
    return d - timedelta(days=delta)


def week_range(d: date) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(week_start(d), time(0, 0))
    end_dt = start_dt + timedelta(days=7)
    return start_dt, end_dt


def is_night(minute_dt: datetime) -> bool:
    t = minute_dt.time()
    return (t >= time(22, 0)) or (t < time(6, 0))

# workpay/time_utils.py (맨 아래 쯤에 추가)

def in_time_window(t: time, start: time, end: time) -> bool:
    """
    start<=end: [start, end)
    start>end : (자정 넘김) [start, 24:00) U [00:00, end)
    """
    if start <= end:
        return start <= t < end
    return (t >= start) or (t < end)


def is_within_schedule(minute_dt: datetime, start_t: time, end_t: time) -> bool:
    return in_time_window(minute_dt.time(), start_t, end_t)
