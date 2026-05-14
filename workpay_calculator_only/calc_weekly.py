from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple, Optional
from config import WEEK_LIMIT_40_MIN, DAY_LIMIT_MIN
from time_utils import is_night as is_night_time


def parse_time(s: str) -> time:
    """HH:MM 형식 문자열을 time 객체로 변환"""
    return datetime.strptime(s, "%H:%M").time()


def minutes_between_dt(a: datetime, b: datetime) -> int:
    """두 datetime 사이의 분 수"""
    return int((b - a).total_seconds() // 60)


# is_night 함수는 time_utils에서 import하여 사용


STEP_MIN = 30


def required_break_minutes(work_minutes: int) -> int:
    """필요한 휴게시간 계산 (4시간마다 30분씩 추가)"""
    # 4시간 초과: 30분
    # 8시간 초과: 60분 (30분 + 30분)
    # 12시간 초과: 90분 (30분 + 30분 + 30분)
    # ...
    if work_minutes <= 4 * 60:
        return 0
    # 4시간마다 30분씩 추가
    break_minutes = ((work_minutes - 1) // (4 * 60)) * 30
    return break_minutes


class WorkSegment:
    """근무 시간대 세그먼트"""
    def __init__(self, start_time: str, end_time: str, is_holiday: bool = False):
        self.start_time = parse_time(start_time)
        self.end_time = parse_time(end_time)
        self.is_holiday = is_holiday

    def get_datetime_range(self, work_date: date) -> Tuple[datetime, datetime]:
        """해당 날짜의 datetime 범위 반환"""
        start_dt = datetime.combine(work_date, self.start_time)
        end_dt = datetime.combine(work_date, self.end_time)
        # 자정을 넘기는 경우 (종료가 같으면 익일로 처리)
        if self.end_time <= self.start_time:
            end_dt += timedelta(days=1)
        return start_dt, end_dt


class DayWork:
    """하루 근무 정보"""
    def __init__(self, work_date: date, segments: List[WorkSegment], is_holiday: bool = False):
        self.work_date = work_date
        self.segments = segments
        self.is_holiday = is_holiday  # 해당 날짜가 휴일인지
        self.is_off = len(segments) == 0

    def total_work_minutes(self) -> int:
        """총 근무 시간(분)"""
        total = 0
        for seg in self.segments:
            start_dt, end_dt = seg.get_datetime_range(self.work_date)
            total += minutes_between_dt(start_dt, end_dt)
        return total


class WeekWork:
    """주간 근무 정보"""
    def __init__(self, week_start_date: date, days: List[DayWork]):
        self.week_start_date = week_start_date
        self.days = days  # 월~일 순서
        # 날짜별 휴일 정보 딕셔너리 (각 분의 실제 날짜 기준으로 휴일 판단용)
        self.holiday_map: Dict[date, bool] = {day.work_date: day.is_holiday for day in days}

    def total_work_minutes(self) -> int:
        """주간 총 근무 시간(분)"""
        return sum(day.total_work_minutes() for day in self.days if not day.is_off)

    def exceeds_40_hours(self) -> bool:
        """주 40시간 초과 여부"""
        return self.total_work_minutes() > WEEK_LIMIT_40_MIN


class MinuteInfo:
    """1분 단위 근무 정보"""
    def __init__(self, minute_dt: datetime, is_break: bool = False):
        self.minute_dt = minute_dt
        self.is_break = is_break
        self.is_overtime = False  # 연장근로
        self.is_night = False  # 야간근로
        self.is_holiday = False  # 휴일근로
        self.holiday_base_date: Optional[date] = None  # 휴일근로 귀속 날짜
        self.holiday_work_minutes = 0  # 해당 날짜의 휴일근로 누적 분
        self.is_previous_day_overtime = False  # 전일 연장 여부 (행정해석 반영)

    def calculate_multiplier(self) -> float:
        """가산수당 배수 계산
        
        기준:
        - 연장만: 1.5배 (1.0 + 0.5)
        - 야간만: 1.5배 (1.0 + 0.5)
        - 휴일(8h 이내)만: 1.5배 (1.0 + 0.5)
        - 휴일(8h 초과)만: 2.0배 (1.0 + 0.5 + 0.5)
        - 연장+야간: 2.0배 (1.0 + 0.5 + 0.5)
        - 휴일(8h 이내)+야간: 2.0배 (1.0 + 0.5 + 0.5)
        - 휴일(8h 초과)+야간: 2.5배 (1.0 + 1.0 + 0.5)
        
        주의: 휴일(8h 초과)는 휴일근로(50%) + 연장근로(50%)로 2.0배 표시
        """
        if self.is_break:
            return 0.0
        
        base = 1.0
        
        # 휴일 가산 계산
        holiday_premium = 0.0
        if self.is_holiday:
            # 휴일근로는 0.5 가산으로 표시
            holiday_premium = 0.5
        
        # 연장근로 가산
        overtime_premium = 0.0
        if self.is_overtime:
            overtime_premium = 0.5
        
        night_premium = 0.5 if self.is_night else 0.0
        
        # 총 가산수당 계산
        total = base + overtime_premium + night_premium + holiday_premium
        
        # 최대 2.5배로 캡
        return min(total, 2.5)

    def get_bucket(self) -> str:
        """ERP 버킷 분류"""
        mult = self.calculate_multiplier()
        if mult <= 1.0:
            return "base"
        elif mult <= 1.5:
            return "m15"
        elif mult <= 2.0:
            return "m20"
        else:
            return "m25"
    
    def get_calculation_explanation(self) -> str:
        """가산수당 계산 근거 설명 문자열 생성"""
        if self.is_break:
            return "휴게시간"
        
        parts = []
        base = 1.0
        
        # 휴일 가산 계산
        holiday_premium = 0.0
        if self.is_holiday:
            holiday_premium = 0.5
            parts.append("휴일근로 +50%")
        
        # 연장근로 가산
        overtime_premium = 0.0
        if self.is_overtime:
            overtime_premium = 0.5
            parts.append("연장근로 +50%")
        
        # 야간근로 가산
        night_premium = 0.5 if self.is_night else 0.0
        if self.is_night:
            parts.append("야간근로 +50%")
        
        # 총 배수 계산
        total = base + overtime_premium + night_premium + holiday_premium
        total = min(total, 2.5)
        
        # 설명 문자열 생성
        if not parts:
            return f"기본 {base:.1f}배"

        explanation = f"기본 {base:.1f}배"
        for part in parts:
            explanation += f"\n+ {part}"
        explanation += f"\n= 총 {total:.1f}배"
        return explanation


def optimize_break_placement_for_segment(
    segment_minute_infos: List[MinuteInfo], 
    required_break: int,
    week_work: WeekWork
) -> List[Tuple[datetime, datetime]]:
    """세그먼트별 휴게시간을 4시간 구간마다 30분씩 배치
    
    배치 규칙:
    - 4시간 근무 후 바로 30분 휴게
    - 예: 09:00~18:00 근무 → 09:00~13:00 근무, 13:00~13:30 휴게, 13:30~17:30 근무, 17:30~18:00 휴게
    """
    if required_break == 0:
        return []

    # 세그먼트 내 모든 근무 시간대를 하나의 리스트로 정렬
    all_work_minutes = sorted([info.minute_dt for info in segment_minute_infos if not info.is_break])
    if len(all_work_minutes) == 0:
        return []
    
    # 시작 시간과 종료 시간
    segment_start = all_work_minutes[0]
    segment_end = all_work_minutes[-1] + timedelta(minutes=STEP_MIN)
    
    break_blocks: List[Tuple[datetime, datetime]] = []
    BREAK_INTERVAL_MIN = 4 * 60  # 4시간
    BREAK_DURATION_MIN = 30  # 30분
    
    # 필요한 휴게 개수 계산 (30분씩)
    num_breaks = required_break // BREAK_DURATION_MIN
    
    # 현재 시간 추적 (휴게 후 재개 시간)
    current_time = segment_start
    
    # 각 4시간 지점마다 휴게 배치
    for break_idx in range(num_breaks):
        # 4시간 근무 후 휴게 시작
        break_start = current_time + timedelta(minutes=BREAK_INTERVAL_MIN)
        break_end = break_start + timedelta(minutes=BREAK_DURATION_MIN)
        
        # 세그먼트 종료 시간을 넘지 않도록 체크
        if break_start >= segment_end:
            # 더 이상 휴게를 배치할 수 없음
            break
        
        # 휴게 종료 시간이 세그먼트를 넘으면 조정
        if break_end > segment_end:
            # 마지막 가능한 위치에 배치
            break_end = segment_end
            break_start = break_end - timedelta(minutes=BREAK_DURATION_MIN)
            if break_start <= current_time:
                # 배치 불가능한 경우 스킵
                break
        
        break_blocks.append((break_start, break_end))
        
        # 다음 근무 시작 시간 업데이트 (휴게 종료 후)
        current_time = break_end
    
    return break_blocks


def optimize_break_placement(day_work: DayWork, minute_infos: List[MinuteInfo]) -> List[Tuple[datetime, datetime]]:
    """휴게시간을 4시간 구간마다 30분씩 배치
    
    배치 규칙:
    - 4시간 근무 후 바로 30분 휴게
    - 예: 09:00~18:00 근무 → 09:00~13:00 근무, 13:00~13:30 휴게, 13:30~17:30 근무, 17:30~18:00 휴게
    """
    required_break = required_break_minutes(day_work.total_work_minutes())
    if required_break == 0:
        return []

    # 모든 근무 시간대를 하나의 리스트로 정렬
    all_work_minutes = sorted([info.minute_dt for info in minute_infos if not info.is_break])
    if len(all_work_minutes) == 0:
        return []
    
    # 시작 시간과 종료 시간
    day_start = all_work_minutes[0]
    day_end = all_work_minutes[-1] + timedelta(minutes=STEP_MIN)
    
    break_blocks: List[Tuple[datetime, datetime]] = []
    BREAK_INTERVAL_MIN = 4 * 60  # 4시간
    BREAK_DURATION_MIN = 30  # 30분
    
    # 필요한 휴게 개수 계산 (30분씩)
    num_breaks = required_break // BREAK_DURATION_MIN
    
    # 현재 시간 추적 (휴게 후 재개 시간)
    current_time = day_start
    
    # 각 4시간 지점마다 휴게 배치
    for break_idx in range(num_breaks):
        # 4시간 근무 후 휴게 시작
        break_start = current_time + timedelta(minutes=BREAK_INTERVAL_MIN)
        break_end = break_start + timedelta(minutes=BREAK_DURATION_MIN)
        
        # 일일 종료 시간을 넘지 않도록 체크
        if break_start >= day_end:
            # 더 이상 휴게를 배치할 수 없음
            break
        
        # 휴게 종료 시간이 일일 종료를 넘으면 조정
        if break_end > day_end:
            # 마지막 가능한 위치에 배치
            break_end = day_end
            break_start = break_end - timedelta(minutes=BREAK_DURATION_MIN)
            if break_start <= current_time:
                # 배치 불가능한 경우 스킵
                break
        
        break_blocks.append((break_start, break_end))
        
        # 다음 근무 시작 시간 업데이트 (휴게 종료 후)
        current_time = break_end
    
    return break_blocks


def calculate_week_work(week_work: WeekWork, normal_start_hhmm: str = "09:00", normal_end_hhmm: str = "18:00") -> Dict:
    """주간 근무 계산 및 결과 반환"""
    normal_start = parse_time(normal_start_hhmm)
    normal_end = parse_time(normal_end_hhmm)
    week_window_start = datetime.combine(week_work.week_start_date, time(0, 0))
    week_window_end = week_window_start + timedelta(days=7)
    
    # 일별 결과
    day_results: List[Dict] = []
    
    # 일별 실근로 시간 저장 (휴게 제외)
    day_work_minutes_list: List[int] = []
    
    # 일별 분 정보 저장 (후속 연장근로/휴일근로 판단용)
    minute_infos_by_day: List[List[MinuteInfo]] = []
    
    # 1단계: 모든 날짜의 분 정보를 생성하고 휴게를 반영
    for day_work in week_work.days:
        if day_work.is_off:
            day_work_minutes_list.append(0)
            minute_infos_by_day.append([])
            continue
        
        # 해당 날짜의 모든 분 정보 생성 (먼저 휴게 없이)
        minute_infos: List[MinuteInfo] = []
        # 각 세그먼트별로 분 정보를 그룹화 (세그먼트별 휴게시간 배치용)
        segment_minute_infos: List[List[MinuteInfo]] = []
        
        for seg in day_work.segments:
            segment_info_list: List[MinuteInfo] = []
            start_dt, end_dt = seg.get_datetime_range(day_work.work_date)
            current = start_dt
            while current < end_dt:
                info = MinuteInfo(current)
                
                # 야간근로
                info.is_night = is_night_time(current)
                
                actual_date = current.date()
                # 행정해석 반영: 날짜 경계를 넘는 근무 처리
                # 근기68207-402, 2003.3.31 해석:
                # 역일(00:00)을 넘어 계속 근로가 이어지는 경우에는 이를 전일의 근로의 연장으로 보아야 하나,
                # 익일의 소정근로시간대(시업시각)까지 계속 이어지는 경우에는
                # 익일 시업시각 이후의 근로는 익일의 소정근로이므로 전일의 근로의 연장으로는 볼 수 없음
                # 
                # 즉, 익일 시업시각 이전까지만 전일 연장으로 처리하고,
                # 익일 시업시각 이후는 익일 근로로 처리
                info.is_previous_day_overtime = False  # 전일 연장 여부 플래그
                preholiday_into_holiday = False
                treat_as_holiday_from_next_start = False
                if actual_date != day_work.work_date:
                    # 날짜 경계를 넘는 경우 (익일)
                    # 전일 근로가 휴일로 넘어가는 경우는 휴일근로로 보지 않음
                    # (연속된 하나의 근로로 보고 연장/야간만 적용)
                    next_day_is_holiday = week_work.holiday_map.get(actual_date, False)
                    preholiday_into_holiday = next_day_is_holiday and not day_work.is_holiday
                    if preholiday_into_holiday:
                        # 익일이 휴일인 경우, 시업시각 이전은 전일 연장,
                        # 시업시각 이후는 익일(휴일) 근로로 처리
                        next_day_normal_start_dt = datetime.combine(actual_date, normal_start)
                        if current < next_day_normal_start_dt:
                            info.is_previous_day_overtime = True
                        else:
                            treat_as_holiday_from_next_start = True
                    else:
                        # 익일의 시업시각 확인
                        next_day_normal_start_dt = datetime.combine(actual_date, normal_start)
                        if current < next_day_normal_start_dt:
                            # 익일 시업시각 이전: 전일 근로의 연장으로 처리
                            info.is_previous_day_overtime = True
                        # 익일 시업시각 이후: 익일 근로로 처리 (전일 연장이 아님)
                
                # 휴일근로 판단: 기본은 각 분의 실제 날짜 기준 (00시 기준)
                # 단, 전일이 휴일이고 익일 시업시각 이전인 경우에는 전일(휴일) 근로로 귀속
                if actual_date in week_work.holiday_map:
                    info.is_holiday = week_work.holiday_map[actual_date]
                else:
                    # 주간 범위를 벗어난 경우 (이론적으로는 발생하지 않아야 함)
                    info.is_holiday = False
                
                # 전일이 휴일인 경우, 익일 시업시각 이전 근로는 휴일근로로 처리
                if info.is_previous_day_overtime and day_work.is_holiday:
                    info.is_holiday = True
                    info.holiday_base_date = day_work.work_date
                
                # 평일에서 휴일로 넘어간 연속 근로:
                # - 시업시각 이전은 휴일근로로 보지 않음
                # - 시업시각 이후는 익일(휴일) 근로로 처리
                if preholiday_into_holiday and not treat_as_holiday_from_next_start:
                    info.is_holiday = False
                    info.holiday_base_date = None
                
                minute_infos.append(info)
                segment_info_list.append(info)
                current += timedelta(minutes=STEP_MIN)
            
            segment_minute_infos.append(segment_info_list)

        # 각 세그먼트별로 독립적으로 휴게시간 배치
        # 세그먼트 간 간격이 충분히 떨어져 있으면 각각 독립적으로 처리
        all_break_blocks: List[Tuple[datetime, datetime]] = []
        
        for seg_idx, seg_info_list in enumerate(segment_minute_infos):
            # 세그먼트의 근무 시간 계산
            seg_work_minutes = len(seg_info_list) * STEP_MIN
            seg_required_break = required_break_minutes(seg_work_minutes)
            
            if seg_required_break > 0:
                # 세그먼트별 휴게시간 배치
                seg_break_blocks = optimize_break_placement_for_segment(
                    seg_info_list, seg_required_break, week_work
                )
                all_break_blocks.extend(seg_break_blocks)
        
        # 휴게시간 배치 (먼저 배치해야 실근로 시간을 정확히 계산 가능)
        for break_start, break_end in all_break_blocks:
            current = break_start
            while current < break_end:
                # 해당 분 찾아서 휴게 표시
                for info in minute_infos:
                    if info.minute_dt == current:
                        info.is_break = True
                        break
                current += timedelta(minutes=STEP_MIN)
        
        # 실근로 시간 계산 (휴게 제외)
        work_min = sum(STEP_MIN for m in minute_infos if not m.is_break)
        day_work_minutes_list.append(work_min)
        minute_infos_by_day.append(minute_infos)
    
    # 주간 총 근무 시간 계산
    total_week_work_min = sum(day_work_minutes_list)
    
    # 일별 초과시간 합계 계산 (행정해석 반영: 전일 귀속 포함)
    daily_work_min_by_date: Dict[date, int] = {}
    daily_base_min_by_date: Dict[date, int] = {}
    for day_idx, minute_infos in enumerate(minute_infos_by_day):
        day_work = week_work.days[day_idx]
        for info in minute_infos:
            if info.is_break:
                continue
            if not (week_window_start <= info.minute_dt < week_window_end) and not info.is_previous_day_overtime:
                continue
            minute_date = info.minute_dt.date()
            if info.is_previous_day_overtime and info.minute_dt.time() < normal_start:
                minute_date = minute_date - timedelta(days=1)
            base_date = day_work.work_date if info.is_previous_day_overtime else minute_date
            daily_work_min_by_date[base_date] = daily_work_min_by_date.get(base_date, 0) + STEP_MIN
            if (info.minute_dt < week_window_end) and (not info.is_holiday) and (not info.is_night):
                daily_base_min_by_date[base_date] = daily_base_min_by_date.get(base_date, 0) + STEP_MIN
    
    # 주 40시간 초과분 계산 (연장이 아닌 모든 시간 기준, 일일 8시간 상한 적용)
    weekly_base_min_for_overtime = sum(
        min(work_min, DAY_LIMIT_MIN) for work_min in daily_work_min_by_date.values()
    )
    weekly_overtime_min = max(0, weekly_base_min_for_overtime - WEEK_LIMIT_40_MIN)
    
    daily_overtime_sum_min = 0
    for work_min in daily_work_min_by_date.values():
        daily_overtime_sum_min += max(0, work_min - DAY_LIMIT_MIN)
    
    # 실제 연장근로 시간 = 일별 초과 + 주 40시간 초과(일일 8시간 초과분 제외 기준)
    actual_overtime_min = daily_overtime_sum_min + weekly_overtime_min
    
    # 2단계: 분 단위 연장근로 판단 (일별 기준 우선, 주간 기준은 남은 분량만)
    daily_count_by_date: Dict[date, int] = {}
    weekly_base_count = 0
    remaining_weekly_overtime = weekly_overtime_min
    
    # 주간 전체를 시간순으로 정렬하여 일괄 판정
    all_overtime_minutes: List[Tuple[datetime, date, bool, MinuteInfo]] = []
    for day_idx, minute_infos in enumerate(minute_infos_by_day):
        day_work = week_work.days[day_idx]
        for info in minute_infos:
            if info.is_break:
                continue
            if not (week_window_start <= info.minute_dt < week_window_end) and not info.is_previous_day_overtime:
                continue
            all_overtime_minutes.append((info.minute_dt, day_work.work_date, day_work.is_holiday, info))
    
    all_overtime_minutes.sort(key=lambda x: x[0])
    
    for _, work_date, is_day_holiday, info in all_overtime_minutes:
        minute_date = info.minute_dt.date()
        if info.is_previous_day_overtime and info.minute_dt.time() < normal_start:
            minute_date = minute_date - timedelta(days=1)
        base_date = work_date if info.is_previous_day_overtime else minute_date
        daily_count_by_date[base_date] = daily_count_by_date.get(base_date, 0) + STEP_MIN
        is_daily_overtime = daily_count_by_date[base_date] > DAY_LIMIT_MIN
        if not is_daily_overtime:
            weekly_base_count += STEP_MIN
        
        is_weekly_overtime = weekly_base_count > WEEK_LIMIT_40_MIN
        
        info.is_overtime = is_daily_overtime
        if (
            info.is_previous_day_overtime
            and is_day_holiday
            and info.minute_dt.time() < normal_start
            and (
                daily_count_by_date[base_date] > DAY_LIMIT_MIN
                or weekly_base_count > WEEK_LIMIT_40_MIN
            )
        ):
            info.is_overtime = True
        elif is_weekly_overtime and not info.is_overtime and remaining_weekly_overtime > 0:
            info.is_overtime = True
            remaining_weekly_overtime -= STEP_MIN
    
    # 주 40시간 기준(1.0배 시간만) 집계용 계산
    weekly_base_display_by_date: Dict[date, int] = {}
    for day_idx, minute_infos in enumerate(minute_infos_by_day):
        day_work = week_work.days[day_idx]
        for info in minute_infos:
            if info.is_break:
                continue
            minute_date = info.minute_dt.date()
            if info.is_previous_day_overtime and info.minute_dt.time() < normal_start:
                minute_date = minute_date - timedelta(days=1)
            base_date = day_work.work_date if info.is_previous_day_overtime else minute_date
            if info.minute_dt < week_window_end and info.get_bucket() == "base":
                weekly_base_display_by_date[base_date] = weekly_base_display_by_date.get(base_date, 0) + STEP_MIN
    weekly_base_min_display = sum(
        min(work_min, DAY_LIMIT_MIN) for work_min in weekly_base_display_by_date.values()
    )

    # 3단계: 일별 결과 생성
    for day_idx, day_work in enumerate(week_work.days):
        if day_work.is_off:
            day_results.append({
                "date": day_work.work_date.isoformat(),
                "is_holiday": day_work.is_holiday,
                "is_off": True,
                "work_min": 0,
                "break_min": 0,
                "overtime_min": 0,
                "bucket_15_min": 0,
                "bucket_20_min": 0,
                "bucket_25_min": 0,
                "timeline": []
            })
            continue
        
        minute_infos = minute_infos_by_day[day_idx]
        
        # 휴일근로 누적 분 계산 (휴게 제외)
        # 날짜 경계를 넘는 근무를 고려하여, 각 분의 실제 날짜 기준으로 휴일근로 누적
        # 같은 날짜 내에서만 누적 (00시 기준으로 날짜가 바뀌면 리셋)
        current_date_holiday_min: Dict[date, int] = {}  # 날짜별 휴일근로 누적 분
        for info in minute_infos:
            if info.is_break:
                continue
            actual_date = info.holiday_base_date or info.minute_dt.date()
            if info.is_holiday:
                # 해당 날짜의 휴일근로 누적 분 증가
                if actual_date not in current_date_holiday_min:
                    current_date_holiday_min[actual_date] = 0
                current_date_holiday_min[actual_date] += STEP_MIN
                info.holiday_work_minutes = current_date_holiday_min[actual_date]
            else:
                # 휴일이 아닌 경우, 해당 날짜의 마지막 휴일근로 누적 분 유지
                if actual_date in current_date_holiday_min:
                    info.holiday_work_minutes = current_date_holiday_min[actual_date]
                else:
                    info.holiday_work_minutes = 0

        # 실근로 시간 (휴게 제외) - 주간 창 내만 집계
        work_min = sum(
            STEP_MIN for m in minute_infos
            if not m.is_break and (week_window_start <= m.minute_dt < week_window_end)
        )
        break_min = sum(
            STEP_MIN for m in minute_infos
            if m.is_break and (week_window_start <= m.minute_dt < week_window_end)
        )
        overtime_min = sum(
            STEP_MIN for m in minute_infos
            if (not m.is_break)
            and m.is_overtime
            and (week_window_start <= m.minute_dt < week_window_end)
        )
        
        # ERP 버킷 집계
        bucket_15_min = 0
        bucket_20_min = 0
        bucket_25_min = 0
        
        for info in minute_infos:
            if info.is_break:
                continue
            if not (week_window_start <= info.minute_dt < week_window_end):
                continue
            bucket = info.get_bucket()
            if bucket == "m15":
                bucket_15_min += STEP_MIN
            elif bucket == "m20":
                bucket_20_min += STEP_MIN
            elif bucket == "m25":
                bucket_25_min += STEP_MIN

        # 타임라인 생성 (세그먼트로 압축, 휴게 포함)
        # 날짜 경계를 넘는 근무를 고려하여 시작 날짜 기준으로 타임라인 생성
        timeline_segments = []
        max_timeline_minutes = 1440  # 기본 24시간
        has_admin_interpretation = any(info.is_previous_day_overtime for info in minute_infos)
        if minute_infos:
            # 타임라인 생성을 위해 시간순으로 정렬 (중요: 여러 세그먼트가 있을 때 시간순 정렬 필요)
            sorted_minute_infos = sorted(minute_infos, key=lambda info: info.minute_dt)
            
            # 시작 날짜의 첫 번째 분 (타임라인 기준점)
            timeline_base_date = day_work.work_date
            timeline_base_datetime = datetime.combine(timeline_base_date, time(0, 0))
            
            # 먼저 모든 세그먼트를 생성하고, 가장 마지막 세그먼트의 끝 위치를 확인
            max_end_minutes = 0
            
            i = 0
            while i < len(sorted_minute_infos):
                info = sorted_minute_infos[i]
                is_break = info.is_break
                if is_break:
                    bucket = "break"
                else:
                    bucket = info.get_bucket()
                base_flags = (info.is_overtime, info.is_holiday, info.is_night)
                
                start_min = i
                j = i + 1
                while j < len(sorted_minute_infos):
                    next_info = sorted_minute_infos[j]
                    next_is_break = next_info.is_break
                    next_bucket = "break" if next_is_break else next_info.get_bucket()
                    
                    # 같은 종류(휴게/근무)이고 같은 버킷이면 계속
                    if is_break == next_is_break and bucket == next_bucket:
                        if is_break:
                            # 휴게시간은 시간상 연속되어야 함
                            expected_next_time = sorted_minute_infos[j-1].minute_dt + timedelta(minutes=STEP_MIN)
                            if next_info.minute_dt == expected_next_time:
                                j += 1
                                continue
                            break
                        next_flags = (next_info.is_overtime, next_info.is_holiday, next_info.is_night)
                        if next_flags == base_flags:
                            # 시간상 연속되어야 함 (STEP_MIN 간격)
                            expected_next_time = sorted_minute_infos[j-1].minute_dt + timedelta(minutes=STEP_MIN)
                            if next_info.minute_dt == expected_next_time:
                                j += 1
                                continue
                            break
                        break
                    else:
                        break
                
                # 분을 시간으로 변환
                start_dt = sorted_minute_infos[start_min].minute_dt
                end_dt = sorted_minute_infos[j-1].minute_dt + timedelta(minutes=STEP_MIN)
                
                # 시작 날짜 기준으로 분 차이 계산 (날짜 경계를 넘는 경우도 처리)
                start_minutes_from_base = int((start_dt - timeline_base_datetime).total_seconds() // 60)
                duration_min = (j - start_min) * STEP_MIN
                end_minutes_from_base = start_minutes_from_base + duration_min
                
                # 가장 마지막 세그먼트의 끝 위치 추적
                max_end_minutes = max(max_end_minutes, end_minutes_from_base)
                
                # 레이블 생성: 날짜 경계를 넘는 경우에만 날짜 표시
                start_date = start_dt.date()
                end_date = end_dt.date()
                if start_date == end_date and start_date == day_work.work_date:
                    # 같은 날짜(근무 시작일 기준)면 시간만 표시
                    label = f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
                else:
                    # 날짜가 근무 시작일과 다르면 날짜도 표시
                    label = f"{start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%m/%d %H:%M')}"
                
                # 휴일 표시 (근무 일시 / 타임라인에서 확인 가능하도록)
                if day_work.is_holiday:
                    label = f"[휴일] {label}"
                
                # 가산수당 계산 근거 설명 생성 (첫 번째 분 정보 사용)
                calculation_info = ""
                if not is_break and start_min < len(sorted_minute_infos):
                    first_info = sorted_minute_infos[start_min]
                    calculation_info = first_info.get_calculation_explanation()
                
                timeline_segments.append({
                    "start_minutes": start_minutes_from_base,  # 임시로 저장 (나중에 비율 계산)
                    "duration_min": duration_min,
                    "kind": bucket,
                    "label": label,
                    "calculation": calculation_info,  # 가산수당 계산 근거
                })
                
                i = j
            
            # 24시간(1440분)을 넘는 경우 타임라인 범위 확장 (6시간 단위로 올림)
            if max_end_minutes > 1440:
                # 6시간(360분) 단위로 올림하여 확장
                max_timeline_minutes = ((max_end_minutes - 1) // 360 + 1) * 360
                # 최대 48시간까지만 표시
                max_timeline_minutes = min(max_timeline_minutes, 2880)
            else:
                max_timeline_minutes = 1440  # 기본 24시간
            
            # 이제 비율을 계산하여 left와 width 설정
            for seg in timeline_segments:
                seg["left"] = round((seg["start_minutes"] / max_timeline_minutes) * 100, 4)
                seg["width"] = round((seg["duration_min"] / max_timeline_minutes) * 100, 4)
                # 임시 필드 제거
                del seg["start_minutes"]
                del seg["duration_min"]
        else:
            # 근무가 없는 경우 기본값
            max_timeline_minutes = 1440

        day_results.append({
            "date": day_work.work_date.isoformat(),
            "is_holiday": day_work.is_holiday,
            "is_off": False,
            "work_min": work_min,
            "break_min": break_min,
            "overtime_min": overtime_min,
            "bucket_15_min": bucket_15_min,
            "bucket_20_min": bucket_20_min,
            "bucket_25_min": bucket_25_min,
            "timeline": timeline_segments,
            "has_admin_interpretation": has_admin_interpretation,
            "max_timeline_hours": max_timeline_minutes // 60  # 타임라인 최대 시간 (템플릿에서 사용)
        })

    # 주간 총 근무 시간 (휴게 제외)
    week_total_min = sum(day.get("work_min", 0) for day in day_results)
    week_overtime_min = sum(day.get("overtime_min", 0) for day in day_results)
    exceeds_40 = week_total_min > WEEK_LIMIT_40_MIN
    
    return {
        "week_total_min": week_total_min,
        "week_overtime_min": week_overtime_min,
        "week_base_min": weekly_base_min_display,
        "exceeds_40": exceeds_40,
        "day_results": day_results,
    }
