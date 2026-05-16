import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Table, Typography, Tag, Space, Divider, Button, Banner, Tooltip,
} from '@douyinfe/semi-ui'
import { saveCalculation, exportCalculation } from '../services/api'
import type { CalcResult, CalcInput } from '../services/api'

const { Title, Text } = Typography
const DAYS = ['월', '화', '수', '목', '금', '토', '일']

interface DayResult {
  date: string
  is_holiday: boolean
  is_off: boolean
  work_min: number
  break_min: number
  overtime_min: number
  bucket_15_min: number
  bucket_20_min: number
  bucket_25_min: number
  timeline?: Array<{ start?: string; end?: string; kind: string; label: string }>
}

function fmtMin(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return m > 0 ? `${h}시간 ${m}분` : `${h}시간`
}

function fmtHour(min: number): string {
  return (min / 60).toFixed(1)
}

const COLORS: Record<string, string> = {
  base: '#adb5bd',
  m15: '#0052d9',
  m20: '#0f8a52',
  m25: '#7c3aed',
  break: '#ffc107',
}

function TimelineBar({ timeline }: { timeline?: Array<{ start?: string; end?: string; kind: string; label: string }> }) {
  if (!timeline || timeline.length === 0) return null

  return (
    <div style={{ position: 'relative', height: 24, background: '#f7f8fa', borderRadius: 4, overflow: 'hidden', border: '1px solid #e5e6eb' }}>
      {timeline.map((seg, i) => {
        if (!seg.start || !seg.end) return null
        const [sh, sm] = seg.start.split(':').map(Number)
        const [eh, em] = seg.end.split(':').map(Number)
        const startMin = sh * 60 + sm
        const endMin = eh * 60 + em
        const left = (startMin / 1440) * 100
        const width = Math.max(((endMin - startMin) / 1440) * 100, 0.5)
        const color = COLORS[seg.kind] || '#ccc'
        return (
          <Tooltip key={i} content={`${seg.start}~${seg.end} (${seg.kind})`}>
            <div style={{
              position: 'absolute', left: `${left}%`, width: `${width}%`,
              top: 0, height: '100%', background: color, borderRadius: 2,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, color: seg.kind === 'break' ? '#333' : '#fff',
              overflow: 'hidden', whiteSpace: 'nowrap',
            }}>
              {width > 3 && seg.label}
            </div>
          </Tooltip>
        )
      })}
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Card style={{ minWidth: 130, textAlign: 'center' }}>
      <Text type="tertiary" style={{ fontSize: 12 }}>{label}</Text>
      <div style={{ fontSize: 24, fontWeight: 700, color: color || '#1f2329', marginTop: 4 }}>{value}</div>
    </Card>
  )
}

function ResultPage() {
  const navigate = useNavigate()
  const [result, setResult] = useState<CalcResult | null>(null)
  const [input, setInput] = useState<CalcInput | null>(null)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const r = sessionStorage.getItem('calc_result')
    const i = sessionStorage.getItem('calc_input')
    if (r) setResult(JSON.parse(r))
    if (i) setInput(JSON.parse(i))
  }, [])

  if (!result || !input) {
    return (
      <Card style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', padding: 60 }}>
        <Title heading={3}>계산 결과가 없습니다</Title>
        <Text type="tertiary" style={{ marginTop: 8, display: 'block' }}>계산기를 통해 결과를 먼저 생성해주세요.</Text>
        <Button style={{ marginTop: 16 }} onClick={() => navigate('/employees')}>직원 목록으로</Button>
      </Card>
    )
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveCalculation(input)
      navigate('/employees/' + encodeURIComponent(input.employee_name))
    } finally {
      setSaving(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await exportCalculation({ input, result, week_end_date: '' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `workpay_${input.employee_name}_${input.week_start_date}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  const dayColumns = [
    {
      title: '요일',
      render: (_: unknown, r: DayResult, idx: number) => (
        <Space>
          <Tag color="blue">{DAYS[idx] || '?'}</Tag>
          {r.is_holiday && <Tag color="red">휴일</Tag>}
          {r.is_off && <Tag>휴무</Tag>}
        </Space>
      ),
    },
    { title: '근무', dataIndex: 'work_min', render: (v: number) => fmtHour(v) },
    { title: '휴게', dataIndex: 'break_min', render: (v: number) => fmtHour(v) },
    { title: '연장', dataIndex: 'overtime_min', render: (v: number) => fmtHour(v) },
    { title: '1.5배', dataIndex: 'bucket_15_min', render: (v: number) => fmtHour(v) },
    { title: '2.0배', dataIndex: 'bucket_20_min', render: (v: number) => fmtHour(v) },
    { title: '2.5배', dataIndex: 'bucket_25_min', render: (v: number) => fmtHour(v) },
    {
      title: '타임라인',
      render: (_: unknown, r: DayResult) => <TimelineBar timeline={r.timeline} />,
    },
  ]

  return (
    <Card style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Space style={{ justifyContent: 'space-between', width: '100%', marginBottom: 16 }}>
        <Title heading={3}>계산 결과</Title>
        <Text type="tertiary">{input.employee_name} | {input.week_start_date}</Text>
      </Space>
      <Divider />

      {result.exceeds_52 && (
        <Banner type="danger" description="주의: 주 52시간 초과 — 해당 주의 총 근로 시간이 52시간을 초과합니다." style={{ marginBottom: 16 }} />
      )}
      {result.overtime_exceeded && (
        <Banner type="warning" description="주의: 연장근로 한도 초과 — 해당 주의 연장근로 시간이 12시간을 초과합니다." style={{ marginBottom: 16 }} />
      )}

      <Space style={{ marginBottom: 24, flexWrap: 'wrap' }}>
        <StatBox label="총 근로" value={fmtMin(result.week_total_min)} />
        <StatBox label="1.5배" value={fmtMin(result.bucket_15_total)} color="#0052d9" />
        <StatBox label="2.0배" value={fmtMin(result.bucket_20_total)} color="#0f8a52" />
        <StatBox label="2.5배" value={fmtMin(result.bucket_25_total)} color="#7c3aed" />
      </Space>

      <Space style={{ marginBottom: 16 }}>
        <Text type="tertiary" strong>범례:</Text>
        <Space>
          <Tag style={{ background: COLORS.base, color: '#333' }}>기본</Tag>
          <Tag color="blue">1.5배</Tag>
          <Tag color="green">2.0배</Tag>
          <Tag style={{ background: COLORS.m25, color: '#fff' }}>2.5배</Tag>
          <Tag style={{ background: COLORS.break, color: '#333' }}>휴게</Tag>
        </Space>
      </Space>

      <Table
        columns={dayColumns}
        dataSource={result.day_results}
        rowKey="date"
        bordered
      />

      <Divider />
      <Space>
        <Button theme="solid" type="primary" onClick={handleSave} loading={saving}>저장</Button>
        <Button theme="solid" onClick={handleExport} loading={exporting}>엑셀 다운로드</Button>
        <Button onClick={() => navigate('/employees')}>직원 목록으로</Button>
        <Button type="tertiary" onClick={() => {
          sessionStorage.removeItem('calc_result')
          sessionStorage.removeItem('calc_input')
          navigate('/employees')
        }}>다시 계산</Button>
      </Space>
    </Card>
  )
}

export default ResultPage
