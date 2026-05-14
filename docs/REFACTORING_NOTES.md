# 리팩토링 및 개선 사항

## 🔴 중요 (보안/버그)

### 1. Secret Key 하드코딩 (app.py)
**문제**: `secret_key`가 하드코딩되어 있음
```python
app.secret_key = "change-this-secret-key"
```
**개선**: 환경 변수나 설정 파일에서 읽어오도록 변경
```python
import os
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
```

### 2. 사용하지 않는 변수 (calc_weekly.py:529)
**문제**: `current_day_overtime_min` 변수가 선언되었지만 사용되지 않음
```python
current_day_overtime_min = max(0, current_day_work_min - DAY_LIMIT_MIN)
```
**개선**: 변수 제거 또는 실제 사용처 추가

## 🟡 중간 (코드 품질)

### 3. 함수 중복 정의
**문제**: `is_night` 함수가 `calc_weekly.py`와 `time_utils.py`에 중복 정의됨
- `calc_weekly.py:16-19`
- `time_utils.py:39-41`

**개선**: `time_utils.py`의 것을 사용하도록 통일
```python
# calc_weekly.py에서
from time_utils import is_night
```

### 4. Bare Except 사용 (routes_calculator.py:23)
**문제**: 너무 일반적인 예외 처리
```python
except:
    pass
```
**개선**: 구체적인 예외 타입 지정
```python
except (ValueError, TypeError) as e:
    flash(f"날짜 형식 오류: {str(e)}", "warning")
    # 또는 로깅
```

### 5. 코드 중복: 실근로 시간 계산
**문제**: `calculate_week_work` 함수에서 실근로 시간을 두 번 계산함
- 1단계: 모든 날짜의 실근로 시간을 먼저 계산 (386-429줄)
- 2단계: 각 날짜별로 다시 계산 (460-567줄)

**개선**: 1단계에서 계산한 결과를 재사용하도록 리팩토링

### 6. 매직 넘버
**문제**: 하드코딩된 숫자들
- `8 * 60`, `40 * 60` 등은 `config.py`에 정의되어 있지만, 일부 곳에서 직접 사용
- `22, 0`, `6, 0` (야간 시간) 등

**개선**: 상수로 정의
```python
# config.py에 추가
NIGHT_START_HOUR = 22
NIGHT_END_HOUR = 6
```

## 🟢 개선 권장 (가독성/유지보수성)

### 7. 타입 힌팅 보완
**문제**: 일부 함수에 타입 힌팅이 부족함
- `calculate_week_work`의 반환 타입이 `Dict`로만 정의됨

**개선**: 더 구체적인 타입 정의
```python
from typing import TypedDict

class WeekWorkResult(TypedDict):
    week_total_min: int
    exceeds_40: bool
    day_results: List[Dict]
```

### 8. 함수 길이
**문제**: `calculate_week_work` 함수가 매우 길음 (200줄 이상)
**개선**: 더 작은 함수로 분리
- `_calculate_day_work_minutes()`: 일별 실근로 시간 계산
- `_determine_overtime_strategy()`: 연장근로 전략 결정
- `_apply_overtime_to_minutes()`: 분별 연장근로 적용

### 9. 변수명 개선
**문제**: 일부 변수명이 모호함
- `minute_infos_temp` → `preliminary_minute_infos` 또는 `day_minute_infos`
- `all_break_blocks_temp` → `preliminary_break_blocks`

### 10. 주석 개선
**문제**: 일부 복잡한 로직에 주석이 부족함
- 연장근로 중복 계산 방지 로직 (534-542줄)
- 타임라인 동적 확장 로직

**개선**: 더 상세한 주석 추가

### 11. 에러 메시지 개선
**문제**: 에러 메시지가 너무 일반적임
```python
flash(f"계산 중 오류가 발생했습니다: {str(e)}", "danger")
```

**개선**: 구체적인 에러 타입별 메시지
```python
if isinstance(e, ValueError):
    flash("입력값 형식이 올바르지 않습니다.", "danger")
elif isinstance(e, KeyError):
    flash("필수 데이터가 누락되었습니다.", "danger")
else:
    flash(f"계산 중 오류가 발생했습니다: {str(e)}", "danger")
```

### 12. 로깅 추가
**문제**: 에러 발생 시 로깅이 없음
**개선**: Python logging 모듈 사용
```python
import logging
logger = logging.getLogger(__name__)

try:
    # ...
except Exception as e:
    logger.error(f"계산 오류: {e}", exc_info=True)
    flash("계산 중 오류가 발생했습니다.", "danger")
```

## 📝 추가 개선 사항

### 13. 단위 테스트 추가
**권장**: 핵심 계산 로직에 대한 단위 테스트 작성
- 연장근로 계산
- 휴게시간 배치
- 가산수당 배수 계산

### 14. 성능 최적화
**문제**: 분 단위로 반복하는 부분이 많음
**개선**: 가능한 경우 벡터화 또는 배치 처리

### 15. 설정 관리
**문제**: 하드코딩된 설정값들
**개선**: `.env` 파일 또는 설정 클래스 사용

### 16. 문서화
**문제**: 함수 docstring이 부족함
**개선**: 모든 공개 함수에 docstring 추가

## 우선순위

1. **즉시 수정**: 보안 문제 (Secret Key)
2. **단기**: 사용하지 않는 변수 제거, 함수 중복 제거, Bare Except 수정
3. **중기**: 코드 중복 제거, 타입 힌팅 보완, 함수 분리
4. **장기**: 단위 테스트, 성능 최적화, 문서화
