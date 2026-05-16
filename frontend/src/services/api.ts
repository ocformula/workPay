import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface Employee {
  name: string
  calc_count: number
  latest_ym: string
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
  input_json?: object
  result_json?: object
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

export interface CalcResult {
  week_total_min: number
  bucket_15_total: number
  bucket_20_total: number
  bucket_25_total: number
  needs_review: boolean
  day_results: Array<{
    date: string
    weekday: string
    work_min: number
    break_min: number
    overtime_min: number
    bucket_15_min: number
    bucket_20_min: number
    bucket_25_min: number
    is_off: boolean
    is_holiday: boolean
    segments?: Array<{ start: string; end: string }>
    display_segments?: Array<{ start: string; end: string }>
    timeline?: Array<{
      kind: string
      label: string
      original_kind?: string
      original_calculation?: string
    }>
  }>
  [key: string]: any
}

export interface CalculationDetail {
  id: number
  week_start_date: string
  week_end_date: string
  normal_start: string
  normal_end: string
  created_at: string
  input: CalcInput
  result: CalcResult
}

export interface ExportPayload {
  input: CalcInput
  result: CalcResult
  week_end_date: string
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

export async function fetchCalculationDetail(name: string, calcId: number): Promise<CalculationDetail> {
  const res = await api.get(`/employees/${encodeURIComponent(name)}/${calcId}`)
  return res.data
}

export async function deleteCalculation(name: string, calcId: number) {
  return api.post(`/employees/${encodeURIComponent(name)}/${calcId}/delete`)
}

export async function exportCalculation(data: ExportPayload): Promise<Blob> {
  const res = await api.post('/calculator/export', data, {
    responseType: 'blob',
  })
  return res.data
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
