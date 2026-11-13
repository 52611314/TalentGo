import type { Envelope } from '../types/api'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message)
  }
}

export function randomKey(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), n => n.toString(16).padStart(2, '0')).join('')
}

export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let result: Response
  try {
    result = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: AbortSignal.timeout(10000) })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '连接暂不可用，请检查本地服务后重试')
  }
  const body = await result.json()
  if (!result.ok) throw new ApiError(result.status, body.error?.code || 'HTTP_ERROR', body.error?.message || '请求失败', body.request_id)
  return (body as Envelope<T>).data
}
