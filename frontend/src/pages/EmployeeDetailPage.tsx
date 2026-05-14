import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Table, Typography, Spin, Empty, Tag, Space, Button } from '@douyinfe/semi-ui'
import { fetchEmployeeCalculations } from '../services/api'
import type { CalculationItem } from '../services/api'

const { Title } = Typography

function fmtMin(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function EmployeeDetailPage() {
  const navigate = useNavigate()
  const { employeeName } = useParams<{ employeeName: string }>()
  const [calculations, setCalculations] = useState<CalculationItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!employeeName) return
    fetchEmployeeCalculations(employeeName)
      .then(setCalculations)
      .finally(() => setLoading(false))
  }, [employeeName])

  const columns = [
    { title: '주차', dataIndex: 'week_start_date' },
    { title: '종료', dataIndex: 'week_end_date' },
    {
      title: '총 근무',
      dataIndex: 'week_total_min',
      align: 'center' as const,
      render: (v: number) => fmtMin(v),
    },
    {
      title: '1.5배',
      dataIndex: 'bucket_15_total',
      align: 'center' as const,
      render: (v: number) => fmtMin(v),
    },
    {
      title: '2.0배',
      dataIndex: 'bucket_20_total',
      align: 'center' as const,
      render: (v: number) => fmtMin(v),
    },
    {
      title: '2.5배',
      dataIndex: 'bucket_25_total',
      align: 'center' as const,
      render: (v: number) => fmtMin(v),
    },
    {
      title: '상태',
      dataIndex: 'needs_review',
      render: (v: boolean) => (
        v ? <Tag color="red">검토 필요</Tag> : <Tag color="green">정상</Tag>
      ),
    },
    {
      title: '액션',
      render: () => (
        <Button size="small" onClick={() => navigate(`/calculator/${encodeURIComponent(employeeName!)}`)}>
          재계산
        </Button>
      ),
    },
  ]

  if (loading) return <Spin spinning style={{ display: 'block', textAlign: 'center', marginTop: 60 }} />

  return (
    <Card>
      <Space style={{ justifyContent: 'space-between', marginBottom: 16 }}>
        <Title heading={3}>{employeeName} - 계산 내역</Title>
        <Button onClick={() => navigate('/employees')}>목록으로</Button>
      </Space>
      {calculations.length === 0 ? (
        <Empty description="계산 내역이 없습니다" />
      ) : (
        <Table columns={columns} dataSource={calculations} rowKey="id" bordered />
      )}
    </Card>
  )
}

export default EmployeeDetailPage
