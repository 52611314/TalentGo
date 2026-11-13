import { request } from './client'
import type { Operation } from '../types/session'

export const getOperation = (id: string, token: string) => request<Operation>(`/operations/${id}`, {}, token)
