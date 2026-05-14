import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import {
  Card, DatePicker, TimePicker, Button, Space, Divider, Typography, Tag,
  Checkbox, Select, TextArea,
} from '@douyinfe/semi-ui'
import { submitCalculation } from '../services/api'

const { Title, Text } = Typography
const DAYS = ['월', '화', '수', '목', '금', '토', '일']

// 30분 간격 시간 옵션
const TIME_OPTIONS = Array.from({ length: 48 }, (_, i) => {
  const h = Math.floor(i / 2)
  const m = (i % 2) * 30
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
})

interface Segment {
  start: string
  end: string
}

interface DayData {
  is_off: boolean
  is_holiday: boolean
  memo: string
  segments: Segment[]
}

function CalculatorPage() {
  const { employeeName } = useParams<{ employeeName: string }>()
  const navigate = useNavigate()
  const [weekStart, setWeekStart] = useState<Date>(() => {
    const today = new Date()
    const monday = new Date(today)
    monday.setDate(today.getDate() - ((today.getDay() + 6) % 7) - 7)
    return monday
  })
  const [normalStart, setNormalStart] = useState('09:00')
  const [normalEnd, setNormalEnd] = useState('18:00')
  const [submitting, setSubmitting] = useState(false)

  // 7일 데이터
  const [days, setDays] = useState<DayData[]>(() =>
    Array.from({ length: 7 }, (_, i) => ({
      is_off: i >= 5, // 토/일 기본 휴무
      is_holiday: i === 6, // 일요일 기본 휴일
      memo: '',
      segments: i < 5 ? [{ start: '09:00', end: '18:00' }] : [],
    }))
  )

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart)
    d.setDate(weekStart.getDate() + i)
    return d
  })

  const updateDay = (idx: number, patch: Partial<DayData>) => {
    setDays(prev => prev.map((d, i) => i === idx ? { ...d, ...patch } : d))
  }

  const addSegment = (dayIdx: number) => {
    setDays(prev => prev.map((d, i) =>
      i === dayIdx ? { ...d, segments: [...d.segments, { start: '09:00', end: '18:00' }] } : d
    ))
  }

  const removeSegment = (dayIdx: number, segIdx: number) => {
    setDays(prev => prev.map((d, i) =>
      i === dayIdx ? { ...d, segments: d.segments.filter((_, si) => si !== segIdx) } : d
    ))
  }

  const updateSegment = (dayIdx: number, segIdx: number, field: 'start' | 'end', value: string) => {
    setDays(prev => prev.map((d, i) => {
      if (i !== dayIdx) return d
      const newSegments = [...d.segments]
      newSegments[segIdx] = { ...newSegments[segIdx], [field]: value }
      return { ...d, segments: newSegments }
    }))
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const payload = {
        employee_name: employeeName ?? '',
        week_start_date: weekStart.toISOString().slice(0, 10),
        normal_start: normalStart,
        normal_end: normalEnd,
        days: days.map((d, i) => ({
          date: weekDates[i].toISOString().slice(0, 10),
          ...d,
        })),
      }
      // Compute result and store for ResultPage
      const res = await submitCalculation(payload)
      sessionStorage.setItem('calc_result', JSON.stringify(res.data))
      sessionStorage.setItem('calc_input', JSON.stringify(payload))
      navigate('/calculator/result')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card style={{ maxWidth: 900, margin: '0 auto' }}>
      <Title heading={3}>{employeeName} - 주간 근무 계산기</Title>
      <Divider />

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>주차 시작일</label>
        <DatePicker
          value={weekStart}
          onChange={(val) => { if (val instanceof Date) setWeekStart(val) }}
          style={{ width: '100%' }}
        />
      </div>
      <Space style={{ marginBottom: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>출근 시간</label>
          <TimePicker
            format="HH:mm"
            value={normalStart}
            onChange={(val) => setNormalStart(val as string)}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>퇴근 시간</label>
          <TimePicker
            format="HH:mm"
            value={normalEnd}
            onChange={(val) => setNormalEnd(val as string)}
          />
        </div>
      </Space>

      <Divider />

      {days.map((day, i) => (
        <div key={i} style={{ marginBottom: 24, padding: 16, border: '1px solid #e5e6eb', borderRadius: 8 }}>
          <Space style={{ marginBottom: 12 }}>
            <Tag color="blue">{DAYS[i]}</Tag>
            <Text strong>{weekDates[i].toLocaleDateString()}</Text>
            <Checkbox
              checked={day.is_off}
              onChange={(e) => updateDay(i, { is_off: e.target.checked })}
            >
              근무 안함
            </Checkbox>
            <Checkbox
              checked={day.is_holiday}
              onChange={(e) => updateDay(i, { is_holiday: e.target.checked })}
            >
              휴일
            </Checkbox>
          </Space>

          {!day.is_off && (
            <>
              {day.segments.map((seg, si) => (
                <Space key={si} style={{ marginBottom: 8 }}>
                  <Select
                    value={seg.start}
                    onChange={(val) => updateSegment(i, si, 'start', val as string)}
                    style={{ width: 120 }}
                  >
                    {TIME_OPTIONS.map(t => (
                      <Select.Option key={t} value={t}>{t}</Select.Option>
                    ))}
                  </Select>
                  <Text>~</Text>
                  <Select
                    value={seg.end}
                    onChange={(val) => updateSegment(i, si, 'end', val as string)}
                    style={{ width: 120 }}
                  >
                    {TIME_OPTIONS.map(t => (
                      <Select.Option key={t} value={t}>{t}</Select.Option>
                    ))}
                  </Select>
                  {day.segments.length > 1 && (
                    <Button size="small" type="danger" onClick={() => removeSegment(i, si)}>
                      ✕
                    </Button>
                  )}
                </Space>
              ))}
              <Button size="small" style={{ marginTop: 4 }} onClick={() => addSegment(i)}>
                + 시간대 추가
              </Button>
              <TextArea
                placeholder="메모"
                value={day.memo}
                onChange={(val) => updateDay(i, { memo: val })}
                style={{ marginTop: 8 }}
                autosize
              />
            </>
          )}
        </div>
      ))}

      <Divider />
      <Space>
        <Button theme="solid" type="primary" onClick={handleSubmit} loading={submitting}>
          계산 및 저장
        </Button>
        <Button onClick={() => navigate('/employees')}>취소</Button>
      </Space>
    </Card>
  )
}

export default CalculatorPage
