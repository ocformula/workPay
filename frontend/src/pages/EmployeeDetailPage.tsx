import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Table, Typography, Tag, Space, Divider, Button, Popconfirm, Select, Empty, Spin,
} from '@douyinfe/semi-ui'
import { fetchEmployeeCalculations, fetchCalculationDetail, deleteCalculation, exportCalculation } from '../services/api'
import type { CalculationItem } from '../services/api'

const { Title, Text } = Typography

function fmtHour(min: number): string {
  return (min / 60).toFixed(1)
}

function MonthFilter({ yearMonths, selectedYm, onSelect }: {
  yearMonths: string[]
  selectedYm: string | null
  onSelect: (ym: string | null) => void
}) {
  const years = [...new Set(yearMonths.map(ym => ym.slice(0, 4)))].sort().reverse()
  const currentYear = selectedYm?.slice(0, 4) || years[0]
  const months = yearMonths
    .filter(ym => ym.startsWith(currentYear))
    .map(ym => ym.slice(5))
    .sort()

  return (
    <Space>
      <Select
        style={{ width: 120 }}
        value={currentYear}
        onChange={(v) => {
          const val = typeof v === 'string' ? v : ''
          onSelect(val ? `${val}-${months[0]}` : null)
        }}
      >
        {years.map(y => <Select.Option key={y} value={y}>{y}년</Select.Option>)}
      </Select>
      <Space>
        <Tag
          color={!selectedYm ? 'blue' : 'white'}
          style={{ cursor: 'pointer', minWidth: 40, textAlign: 'center', fontWeight: !selectedYm ? 600 : 400 }}
          onClick={() => onSelect(null)}
        >
          전체
        </Tag>
        {months.map(m => (
          <Tag
            key={m}
            color={selectedYm === `${currentYear}-${m}` ? 'blue' : 'white'}
            style={{ cursor: 'pointer', minWidth: 40, textAlign: 'center', fontWeight: selectedYm === `${currentYear}-${m}` ? 600 : 400 }}
            onClick={() => onSelect(`${currentYear}-${m}`)}
          >
            {parseInt(m)}월
          </Tag>
        ))}
      </Space>
    </Space>
  )
}

function EmployeeDetailPage() {
  const navigate = useNavigate()
  const { employeeName } = useParams<{ employeeName: string }>()
  const [calculations, setCalculations] = useState<CalculationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedYm, setSelectedYm] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    if (!employeeName) return
    fetchEmployeeCalculations(employeeName)
      .then(data => {
        setCalculations(data)
        if (data.length > 0) {
          setSelectedYm(data[0].week_start_date?.slice(0, 7) || null)
        }
      })
      .finally(() => setLoading(false))
  }, [employeeName])

  const filtered = selectedYm
    ? calculations.filter(c => c.week_start_date?.startsWith(selectedYm))
    : calculations

  const yearMonths = [...new Set(calculations.map(c => c.week_start_date?.slice(0, 7)).filter(Boolean))]

  const loadDetail = async (calcId: number) => {
    if (!employeeName) return
    setExpandedId(calcId)
    setDetailLoading(true)
    try {
      const data = await fetchCalculationDetail(employeeName, calcId)
      setDetail(data)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDelete = async (calcId: number) => {
    if (!employeeName) return
    await deleteCalculation(employeeName, calcId)
    setCalculations(prev => prev.filter(c => c.id !== calcId))
  }

  const handleExport = async () => {
    if (!detail) return
    const blob = await exportCalculation({ input: detail.input, result: detail.result, week_end_date: detail.week_end_date || '' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `workpay_${employeeName}_${detail.week_start_date}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  const columns = [
    { title: '주차', dataIndex: 'week_start_date' },
    { title: '종료', dataIndex: 'week_end_date' },
    { title: '총근무', render: (_: unknown, r: CalculationItem) => fmtHour(r.week_total_min) },
    { title: '1.5배', render: (_: unknown, r: CalculationItem) => fmtHour(r.bucket_15_total) },
    { title: '2.0배', render: (_: unknown, r: CalculationItem) => fmtHour(r.bucket_20_total) },
    { title: '2.5배', render: (_: unknown, r: CalculationItem) => fmtHour(r.bucket_25_total) },
    {
      title: '상태',
      render: (_: unknown, r: CalculationItem) => (
        r.needs_review ? <Tag color="red">검토 필요</Tag> : <Tag color="green">정상</Tag>
      ),
    },
    {
      title: '액션',
      render: (_: unknown, r: CalculationItem) => (
        <Space>
          <Button size="small" onClick={() => loadDetail(r.id)}>상세</Button>
          <Popconfirm title="삭제하시겠습니까?" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" type="danger">삭제</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (loading) return <Spin spinning style={{ display: 'block', textAlign: 'center', marginTop: 60 }} />

  return (
    <Card>
      <Space style={{ justifyContent: 'space-between', width: '100%', marginBottom: 16 }}>
        <Title heading={3}>{employeeName} - 계산 내역</Title>
        <Button onClick={() => navigate('/employees')}>목록으로</Button>
      </Space>

      <MonthFilter yearMonths={yearMonths} selectedYm={selectedYm} onSelect={setSelectedYm} />
      <Divider />

      {filtered.length === 0 ? (
        <Empty description="계산 내역이 없습니다" />
      ) : (
        <Table columns={columns} dataSource={filtered} rowKey="id" bordered />
      )}

      {expandedId && detail && (
        <>
          <Divider />
          <Title heading={4}>상세: {detail.week_start_date} ~ {detail.week_end_date}</Title>
          {detailLoading ? <Spin spinning /> : (
            <>
              <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
                <Card style={{ minWidth: 120, textAlign: 'center' }}>
                  <Text type="tertiary" style={{ fontSize: 12 }}>총 근로</Text>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{fmtHour(detail.result?.week_total_min || 0)}h</div>
                </Card>
                <Card style={{ minWidth: 100, textAlign: 'center' }}>
                  <Text type="tertiary" style={{ fontSize: 12 }}>1.5배</Text>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#0052d9' }}>{fmtHour(detail.result?.bucket_15_total || 0)}h</div>
                </Card>
                <Card style={{ minWidth: 100, textAlign: 'center' }}>
                  <Text type="tertiary" style={{ fontSize: 12 }}>2.0배</Text>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#0f8a52' }}>{fmtHour(detail.result?.bucket_20_total || 0)}h</div>
                </Card>
                <Card style={{ minWidth: 100, textAlign: 'center' }}>
                  <Text type="tertiary" style={{ fontSize: 12 }}>2.5배</Text>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#7c3aed' }}>{fmtHour(detail.result?.bucket_25_total || 0)}h</div>
                </Card>
              </Space>

              <Table
                columns={[
                  { title: '일자', dataIndex: 'date' },
                  { title: '근무', render: (_: any, r: any) => fmtHour(r.work_min) },
                  { title: '휴게', render: (_: any, r: any) => fmtHour(r.break_min) },
                  { title: '연장', render: (_: any, r: any) => fmtHour(r.overtime_min) },
                  { title: '1.5배', render: (_: any, r: any) => fmtHour(r.bucket_15_min) },
                  { title: '2.0배', render: (_: any, r: any) => fmtHour(r.bucket_20_min) },
                  { title: '2.5배', render: (_: any, r: any) => fmtHour(r.bucket_25_min) },
                ]}
                dataSource={detail.result?.day_results || []}
                rowKey="date"
                bordered
              />

              <Space style={{ marginTop: 16 }}>
                <Button theme="solid" onClick={handleExport}>엑셀 다운로드</Button>
                <Button onClick={() => { setExpandedId(null); setDetail(null) }}>닫기</Button>
              </Space>
            </>
          )}
        </>
      )}
    </Card>
  )
}

export default EmployeeDetailPage
