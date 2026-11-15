import { request } from './client'
import type { Identity } from '../types/api'
import type { Profile } from '../types/session'

export const authenticate = (mode: 'login' | 'register', username: string, password: string) => request<Identity & { profile: Profile }>(`/auth/${mode}`, {
  method: 'POST', body: JSON.stringify({ username, password }),
})
export const logout = (token: string) => request<void>('/auth/logout', { method: 'POST' }, token)
export const getIdentity = (token: string) => request<Omit<Identity, 'token' | 'expires_at'>>('/identity/me', {}, token)
