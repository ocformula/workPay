import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Input, Typography, Toast, Space } from '@douyinfe/semi-ui'
import { fetchAdminEmployees, addEmployee, deleteEmployee } from '../services/api'

const { Title } = Typography

interface AdminEmployee {
  id: number
  name: string
  calc_count: number
  trash_count: number
}

function AdminEmployeesPage() {
  const [items, setItems] = useState<AdminEmployee[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')

  useEffect(() => {
    refresh()
  }, [])

  const refresh = () => fetchAdminEmployees().then(setItems)

  const handleAdd = async () => {
    if (!newName.trim()) return
    await addEmployee(newName)
    Toast.success({ content: '추가되었습니다' })
    setNewName('')
    setShowAdd(false)
    refresh()
  }

  const handleDelete = (id: number, name: string) => {
    Modal.confirm({
      title: `${name} 삭제 확인`,
      content: '계산 내역이 있는 직원은 삭제할 수 없습니다.',
      onOk: async () => {
        await deleteEmployee(id, '')
        Toast.success({ content: '삭제되었습니다' })
        refresh()
      },
    })
  }

  const columns = [
    { title: '이름', dataIndex: 'name' },
    { title: '계산 수', dataIndex: 'calc_count', align: 'center' as const },
    { title: '휴지통', dataIndex: 'trash_count', align: 'center' as const },
    {
      title: '액션',
      render: (_: unknown, r: AdminEmployee) => (
        <Button size="small" type="danger" onClick={() => handleDelete(r.id, r.name)}>
          삭제
        </Button>
      ),
    },
  ]

  return (
    <Card>
      <Space style={{ justifyContent: 'space-between', marginBottom: 16 }}>
        <Title heading={3} style={{ margin: 0 }}>직원 관리</Title>
        <Button theme="solid" type="primary" onClick={() => setShowAdd(true)}>
          직원 추가
        </Button>
      </Space>
      <Table columns={columns} dataSource={items} rowKey="id" bordered />
      <Modal
        visible={showAdd}
        title="직원 추가"
        onOk={handleAdd}
        onCancel={() => setShowAdd(false)}
      >
        <Input placeholder="직원명" value={newName} onChange={setNewName} />
      </Modal>
    </Card>
  )
}

export default AdminEmployeesPage
