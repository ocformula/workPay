import os

# App directory and DB location
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "workpay.sqlite3")

# Week starts on Monday (ISO: Monday=0)
WEEK_START_ISO = 0

# Limits
DAY_LIMIT_MIN = 8 * 60
WEEK_LIMIT_40_MIN = 40 * 60
WEEK_LIMIT_52_MIN = 52 * 60

# Break optimization search step
# (휴게 최적화 탐색은 10분 단위)
SEARCH_STEP_MIN = 10  # minutes
BREAK_GUARD_MIN = 60
BREAK_BLOCK_MIN = 30

# Seed employees (first-run convenience)
DEFAULT_EMPLOYEES = [
    "정권희", "강수한", "박종철", "서신영", "이호섭",
    "김영진", "김왕수", "최정엽", "엄두용", "김태원"
]

# 관리자 비밀번호 (환경변수 ADMIN_PASSWORD가 있으면 우선)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "wotjd12!@")

# 근무 입력 드롭다운(30분 간격)
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 30)]

# 정책 옵션:
# 휴일근로가 8시간을 초과한 분(minute)에 대해 휴일 가산을 1.0으로 올릴지(기존 로직),
# 아니면 휴일 가산은 항상 0.5로 두고(일/주 연장 등과의 조합으로만) 처리할지.
HOLIDAY_OVER_8H_EXTRA_PREMIUM = False
