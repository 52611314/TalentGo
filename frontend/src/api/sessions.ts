import { API_BASE, ApiError, request } from './client'
import type { InterviewMessage, InterviewSession, InterviewReport, Page, SkillTrace } from '../types/session'

export const getSession = (id: string, token: string) => request<InterviewSession>(`/sessions/${id}`, {}, token)
export const getMessages = (id: string, token: string, cursor?: string) => request<Page<InterviewMessage>>(
  `/sessions/${id}/messages?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {}, token)
export const getSessions = (token: string, cursor?: string) => request<Page<InterviewSession>>(
  `/sessions?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {}, token)
export const getReport = (id: string, token: string) => request<InterviewReport>(`/sessions/${id}/report`, {}, token)
export const getTrace = (id: string, token: string) => request<Page<SkillTrace>>(`/sessions/${id}/trace`, {}, token)

export async function getExport(id: string, format: 'markdown'|'json', token: string): Promise<Blob> {
  let response: Response
  try { response = await fetch(`${API_BASE}/sessions/${id}/report/export?format=${format}`, {headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(10000)}) }
  catch { throw new ApiError(0,'NETWORK_ERROR','导出连接失败，请重试') }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status,data?.error?.code||'EXPORT_FAILED',data?.error?.message||'导出失败')
  }
  return response.blob()
}
