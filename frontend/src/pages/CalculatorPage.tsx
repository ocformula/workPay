import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import {
  Card, DatePicker, TimePicker, Button, Space, Divider, Typography, Tag,
} from '@douyinfe/semi-ui'
import { submitCalculation } from '../services/api'

const { Title, Text } = Typography
const DAYS = ['월', '화', '수', '목', '금', '토', '일']

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

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart)
    d.setDate(weekStart.getDate() + i)
    return d
  })

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const payload = {
        employee_name: employeeName ?? '',
        week_start_date: weekStart.toISOString().slice(0, 10),
        normal_start: normalStart,
        normal_end: normalEnd,
        days: weekDates.map((d) => ({
          date: d.toISOString().slice(0, 10),
          is_off: false,
          is_holiday: false,
          memo: '',
          segments: [],
        })),
      }
      await submitCalculation(payload)
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

      {weekDates.map((d, i) => {
        const dateStr = d.toISOString().slice(0, 10)
        return (
          <div key={i} style={{ marginBottom: 16 }}>
            <Tag color="blue">{DAYS[i]}</Tag>{' '}
            <Text strong>{dateStr}</Text>
          </div>
        )
      })}

      <Divider />
      <Button theme="solid" type="primary" onClick={handleSubmit} loading={submitting}>
        계산하기
      </Button>
    </Card>
  )
}

export default CalculatorPage
