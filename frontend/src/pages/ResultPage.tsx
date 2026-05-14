import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Table, Typography, Tag, Space, Divider, Button } from '@douyinfe/semi-ui'

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
}

interface CalcResult {
  week_total_min: number
  bucket_15_total: number
  bucket_20_total: number
  bucket_25_total: number
  day_results: DayResult[]
}

function fmtMin(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return m > 0 ? `${h}시간 ${m}분` : `${h}시간`
}

function ResultPage() {
  const navigate = useNavigate()
  const [result, setResult] = useState<CalcResult | null>(null)

  useEffect(() => {
    const raw = sessionStorage.getItem('calc_result')
    if (raw) setResult(JSON.parse(raw))
  }, [])

  if (!result) {
    return (
      <Card style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', padding: 60 }}>
        <Title heading={3}>계산 결과가 없습니다</Title>
        <Text type="tertiary" style={{ marginTop: 8, display: 'block' }}>
          계산기를 통해 결과를 먼저 생성해주세요.
        </Text>
        <Button style={{ marginTop: 16 }} onClick={() => navigate('/employees')}>직원 목록으로</Button>
      </Card>
    )
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
    { title: '근로(분)', dataIndex: 'work_min', align: 'center' as const },
    { title: '휴게(분)', dataIndex: 'break_min', align: 'center' as const },
    { title: '연장(분)', dataIndex: 'overtime_min', align: 'center' as const },
    { title: '1.5배', dataIndex: 'bucket_15_min', align: 'center' as const },
    { title: '2.0배', dataIndex: 'bucket_20_min', align: 'center' as const },
    { title: '2.5배', dataIndex: 'bucket_25_min', align: 'center' as const },
  ]

  return (
    <Card style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title heading={3}>계산 결과</Title>
      <Divider />

      <Space style={{ marginBottom: 24 }}>
        <Card style={{ minWidth: 150 }}>
          <Text type="tertiary">총 근로</Text>
          <br /><Title heading={4}>{fmtMin(result.week_total_min)}</Title>
        </Card>
        <Card style={{ minWidth: 120 }}>
          <Text type="tertiary">1.5배</Text>
          <br /><Title heading={4} style={{ color: '#0052d9' }}>{fmtMin(result.bucket_15_total)}</Title>
        </Card>
        <Card style={{ minWidth: 120 }}>
          <Text type="tertiary">2.0배</Text>
          <br /><Title heading={4} style={{ color: '#0f8a52' }}>{fmtMin(result.bucket_20_total)}</Title>
        </Card>
        <Card style={{ minWidth: 120 }}>
          <Text type="tertiary">2.5배</Text>
          <br /><Title heading={4} style={{ color: '#7c3aed' }}>{fmtMin(result.bucket_25_total)}</Title>
        </Card>
      </Space>

      <Table
        columns={dayColumns}
        dataSource={result.day_results.map((d, i) => ({ ...d, _idx: i }))}
        rowKey="date"
        bordered
      />

      <Divider />
      <Space>
        <Button onClick={() => navigate('/employees')}>직원 목록으로</Button>
        <Button type="tertiary" onClick={() => { sessionStorage.removeItem('calc_result'); navigate('/employees') }}>다시 계산</Button>
      </Space>
    </Card>
  )
}

export default ResultPage
