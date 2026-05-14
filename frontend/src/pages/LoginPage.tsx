import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Input, Button, Typography, Toast } from '@douyinfe/semi-ui'
import { loginAdmin } from '../services/api'

const { Title } = Typography

function LoginPage() {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await loginAdmin(password)
      Toast.success({ content: '로그인 되었습니다' })
      navigate('/admin/employees')
    } catch {
      Toast.error({ content: '비밀번호가 올바르지 않습니다' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card style={{ maxWidth: 400, margin: '60px auto' }}>
      <Title heading={3} style={{ textAlign: 'center' }}>관리자 로그인</Title>
      <div style={{ marginTop: 16 }}>
        <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>비밀번호</label>
        <Input
          type="password"
          value={password}
          onChange={setPassword}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
        />
      </div>
      <Button theme="solid" type="primary" onClick={handleSubmit} loading={loading} style={{ width: '100%', marginTop: 16 }}>
        로그인
      </Button>
    </Card>
  )
}

export default LoginPage
