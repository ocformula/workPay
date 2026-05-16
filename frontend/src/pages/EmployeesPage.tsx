import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Typography, Select, Button, Space } from '@douyinfe/semi-ui'
import { fetchEmployees } from '../services/api'
import type { Employee } from '../services/api'

const { Title, Text } = Typography

function EmployeesPage() {
  const navigate = useNavigate()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [selectedName, setSelectedName] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEmployees()
      .then(data => {
        setEmployees(data)
        if (data.length > 0) setSelectedName(data[0].name)
      })
      .finally(() => setLoading(false))
  }, [])

  const selectedEmp = employees.find(e => e.name === selectedName)

  return (
    <>
      <Card style={{ marginBottom: 16 }}>
        <Title heading={3} style={{ marginBottom: 4 }}>WorkPay 주간 계산기</Title>
        <Text type="tertiary">
          주간 근무 시간과 가산수당을 간편하게 계산하고, 직원별 내역을 관리할 수 있습니다.
          {' '}직원 선택 후 근무등록 또는 내역보기를 진행하세요.
        </Text>
      </Card>

      <Card>
        <Title heading={5} style={{ marginBottom: 16 }}>직원 선택</Title>
        {loading ? (
          <Text type="tertiary">로딩 중...</Text>
        ) : employees.length > 0 ? (
          <>
            <Space style={{ flexWrap: 'wrap', alignItems: 'flex-end', gap: 12 }}>
              <div style={{ minWidth: 200 }}>
                <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: 14 }}>직원명</label>
                <Select
                  style={{ width: '100%' }}
                  value={selectedName}
                  onChange={(v) => setSelectedName(typeof v === 'string' ? v : '')}
                >
                  {employees.map(emp => (
                    <Select.Option key={emp.name} value={emp.name}>{emp.name}</Select.Option>
                  ))}
                </Select>
              </div>
              <Space>
                <Button
                  theme="solid"
                  type="primary"
                  onClick={() => navigate('/calculator/' + encodeURIComponent(selectedName))}
                >
                  근무등록
                </Button>
                <Button
                  theme="solid"
                  onClick={() => {
                    const ym = selectedEmp?.latest_ym
                    navigate('/employees/' + encodeURIComponent(selectedName) + (ym ? '?ym=' + ym : ''))
                  }}
                >
                  내역 보기
                </Button>
              </Space>
            </Space>
            <Text type="tertiary" style={{ marginTop: 12, display: 'block', fontSize: 12 }}>
              저장된 주간 건수는 직원 상세 화면에서 확인할 수 있습니다.
            </Text>
          </>
        ) : (
          <Text type="tertiary">등록된 직원이 없습니다. 관리자 페이지에서 직원을 추가하세요.</Text>
        )}
      </Card>
    </>
  )
}

export default EmployeesPage
