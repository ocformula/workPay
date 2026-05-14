import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Layout, Nav } from '@douyinfe/semi-ui'
import EmployeesPage from './pages/EmployeesPage'
import CalculatorPage from './pages/CalculatorPage'
import ResultPage from './pages/ResultPage'
import EmployeeDetailPage from './pages/EmployeeDetailPage'
import LoginPage from './pages/LoginPage'
import AdminEmployeesPage from './pages/AdminEmployeesPage'
import AdminTrashPage from './pages/AdminTrashPage'
import WorkLogPage from './pages/WorkLogPage'

const { Header, Content } = Layout

const navItems = [
  { itemKey: '/employees', text: '직원 목록' },
  { itemKey: '/worklog', text: '근무 로그' },
  { itemKey: '/admin/login', text: '관리자' },
]

function App() {
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ padding: 0 }}>
        <Nav
          mode="horizontal"
          selectedKeys={[location.pathname]}
          header={{ logo: <span style={{ fontWeight: 600, fontSize: 18 }}>WorkPay</span> }}
          items={navItems}
        />
      </Header>
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/employees" replace />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/calculator/:employeeName" element={<CalculatorPage />} />
          <Route path="/calculator/result" element={<ResultPage />} />
          <Route path="/employees/:employeeName" element={<EmployeeDetailPage />} />
          <Route path="/admin/login" element={<LoginPage />} />
          <Route path="/admin/employees" element={<AdminEmployeesPage />} />
          <Route path="/admin/trash" element={<AdminTrashPage />} />
          <Route path="/worklog" element={<WorkLogPage />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default App
