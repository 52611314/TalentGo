import { randomKey, request } from './client'
import type { Identity } from '../types/api'
import type { Profile } from '../types/session'

export const createIdentity = (name: string) => request<Identity & { profile: Profile }>('/identity', {
  method: 'POST', headers: { 'Idempotency-Key': randomKey() }, body: JSON.stringify({ display_name: name }),
})
export const getIdentity = (token: string) => request<Omit<Identity, 'token'>>('/identity/me', {}, token)
