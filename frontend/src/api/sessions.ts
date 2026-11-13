import { request } from './client'
import type { InterviewMessage, InterviewSession, InterviewReport, Page, SkillTrace } from '../types/session'

export const getSession = (id: string, token: string) => request<InterviewSession>(`/sessions/${id}`, {}, token)
export const getMessages = (id: string, token: string, cursor?: string) => request<Page<InterviewMessage>>(
  `/sessions/${id}/messages?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {}, token)
export const getSessions = (token: string, cursor?: string) => request<Page<InterviewSession>>(
  `/sessions?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {}, token)
export const getReport = (id: string, token: string) => request<InterviewReport>(`/sessions/${id}/report`, {}, token)
export const getTrace = (id: string, token: string) => request<Page<SkillTrace>>(`/sessions/${id}/trace`, {}, token)
