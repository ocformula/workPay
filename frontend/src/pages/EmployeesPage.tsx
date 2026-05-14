import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Card, Typography, Spin, Empty } from '@douyinfe/semi-ui'
import { fetchEmployees } from '../services/api'
import type { Employee } from '../services/api'

const { Title, Text } = Typography

function EmployeesPage() {
  const navigate = useNavigate()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEmployees()
      .then(setEmployees)
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    {
      title: '직원명',
      dataIndex: 'name',
      render: (name: string) => (
        <Text
          style={{ cursor: 'pointer', color: '#0366d6' }}
          onClick={() => navigate(`/employees/${encodeURIComponent(name)}`)}
        >
          {name}
        </Text>
      ),
    },
    {
      title: '계산 횟수',
      dataIndex: 'calc_count',
      align: 'center' as const,
    },
    {
      title: '액션',
      render: (_: unknown, record: Employee) => (
        <>
          <a
            style={{ marginRight: 12, cursor: 'pointer' }}
            onClick={() => navigate(`/calculator/${encodeURIComponent(record.name)}`)}
          >
            계산하기
          </a>
          <a onClick={() => navigate(`/employees/${encodeURIComponent(record.name)}`)}>
            내역 보기
          </a>
        </>
      ),
    },
  ]

  if (loading) return <Spin spinning={loading} style={{ display: 'block', textAlign: 'center', marginTop: 60 }} />

  return (
    <Card>
      <Title heading={3} style={{ marginBottom: 16 }}>
        직원 목록
      </Title>
      {employees.length === 0 ? (
        <Empty description="직원이 없습니다" />
      ) : (
        <Table columns={columns} dataSource={employees} rowKey="name" bordered />
      )}
    </Card>
  )
}

export default EmployeesPage
