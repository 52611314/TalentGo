import { request } from './client'
import type { Profile, ProfileInput } from '../types/session'

export const getProfile = (token: string) => request<Profile>('/profile', {}, token)
export const saveProfile = (token: string, fields: ProfileInput, version: number, key: string) => request<Profile>('/profile', {
  method: 'PATCH', headers: { 'Idempotency-Key': key },
  body: JSON.stringify({ ...fields, expected_version: version }),
}, token)
