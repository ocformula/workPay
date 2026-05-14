import { useEffect, useState } from 'react'
import { Card, Table, Button, Typography, Toast, Space } from '@douyinfe/semi-ui'
import { fetchTrash, restoreTrash, purgeTrash } from '../services/api'

const { Title } = Typography

interface TrashItem {
  id: number
  employee_name: string
  week_start_date: string
  week_end_date: string
  deleted_at: string
}

function AdminTrashPage() {
  const [items, setItems] = useState<TrashItem[]>([])

  useEffect(() => {
    refresh()
  }, [])

  const refresh = () => fetchTrash().then(setItems)

  const columns = [
    { title: '직원', dataIndex: 'employee_name' },
    { title: '주차', dataIndex: 'week_start_date' },
    { title: '삭제일', dataIndex: 'deleted_at' },
    {
      title: '액션',
      render: (_: unknown, r: TrashItem) => (
        <Space>
          <Button size="small" onClick={async () => { await restoreTrash(r.id); Toast.success({ content: '복구됨' }); refresh() }}>
            복구
          </Button>
          <Button size="small" type="danger" onClick={async () => { await purgeTrash(r.id); Toast.success({ content: '완전 삭제됨' }); refresh() }}>
            완전 삭제
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Title heading={3}>휴지통</Title>
      <Table columns={columns} dataSource={items} rowKey="id" bordered />
    </Card>
  )
}

export default AdminTrashPage
