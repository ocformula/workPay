import { useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Card, Table, Typography, Spin, Empty } from '@douyinfe/semi-ui'
import { fetchEmployeeCalculations } from '../services/api'
import type { CalculationItem } from '../services/api'

const { Title } = Typography

function EmployeeDetailPage() {
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
    { title: '주차 시작', dataIndex: 'week_start_date' },
    { title: '주차 종료', dataIndex: 'week_end_date' },
    { title: '총 근무(분)', dataIndex: 'week_total_min', align: 'center' as const },
    { title: '1.5배', dataIndex: 'bucket_15_total', align: 'center' as const },
    { title: '2.0배', dataIndex: 'bucket_20_total', align: 'center' as const },
    { title: '2.5배', dataIndex: 'bucket_25_total', align: 'center' as const },
    {
      title: '상태',
      dataIndex: 'needs_review',
      render: (v: boolean) => (v ? '⚠️ 검토 필요' : '✅ 정상'),
    },
  ]

  if (loading) return <Spin spinning style={{ display: 'block', textAlign: 'center', marginTop: 60 }} />

  return (
    <Card>
      <Title heading={3}>{employeeName} - 계산 내역</Title>
      {calculations.length === 0 ? (
        <Empty description="계산 내역이 없습니다" />
      ) : (
        <Table columns={columns} dataSource={calculations} rowKey="id" bordered />
      )}
    </Card>
  )
}

export default EmployeeDetailPage
