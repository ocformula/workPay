import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface Employee {
  name: string
  calc_count: number
}

export interface CalculationItem {
  id: number
  week_start_date: string
  week_end_date: string
  normal_start: string
  normal_end: string
  created_at: string
  week_total_min: number
  bucket_15_total: number
  bucket_20_total: number
  bucket_25_total: number
  needs_review: boolean
  auto_carryover: boolean
  carryover_from?: string
}

export interface CalcInput {
  employee_name: string
  week_start_date: string
  normal_start: string
  normal_end: string
  days: Array<{
    date: string
    is_off: boolean
    is_holiday: boolean
    memo: string
    segments: Array<{ start: string; end: string }>
  }>
}

export async function fetchEmployees(): Promise<Employee[]> {
  const res = await api.get('/employees')
  return res.data
}

export async function fetchEmployeeCalculations(name: string): Promise<CalculationItem[]> {
  const res = await api.get(`/employees/${encodeURIComponent(name)}`)
  return res.data
}

export async function submitCalculation(data: CalcInput) {
  return api.post('/calculator/result', data)
}

export async function saveCalculation(data: CalcInput) {
  return api.post('/calculator/save', data)
}

export async function loginAdmin(password: string) {
  return api.post('/admin/login', { password })
}

export async function logoutAdmin() {
  return api.post('/admin/logout')
}

export async function fetchAdminEmployees() {
  const res = await api.get('/admin/employees')
  return res.data
}

export async function addEmployee(name: string) {
  return api.post('/admin/employees/add', { employee_name: name })
}

export async function deleteEmployee(id: number, password: string) {
  return api.post(`/admin/employees/${id}/delete`, { password })
}

export async function fetchTrash() {
  const res = await api.get('/admin/trash')
  return res.data
}

export async function restoreTrash(id: number) {
  return api.post(`/admin/trash/${id}/restore`)
}

export async function purgeTrash(id: number) {
  return api.post(`/admin/trash/${id}/purge`)
}

export default api
