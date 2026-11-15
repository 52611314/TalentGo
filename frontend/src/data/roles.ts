import { ref } from 'vue'
import { request } from '../api/client'

export interface RoleOption { id: string; label: string; group: string; focus: string; aliases: string[] }
export const roles = ref<RoleOption[]>([])
let pending: Promise<void> | null = null
export function loadRoles() {
  if (roles.value.length) return Promise.resolve()
  if (!pending) pending = request<{ items: RoleOption[] }>('/roles').then(result => { roles.value = result.items }).finally(() => { pending = null })
  return pending
}
export const roleLabel = (role?: string | null) => roles.value.find(item => item.id === role)?.label || (role ? (({frontend:'前端开发工程师',backend:'后端开发工程师'} as Record<string,string>)[role] || role) : '岗位待确认')
export function rolePlan(primary: string | null, secondary: string[], total: number) {
  if (!primary) return []
  if (!secondary.length) return [{ role: primary, question_count: total, primary: true }]
  const main = Math.min(Math.ceil(total * .6), total - secondary.length)
  const remaining = total - main
  return [{ role: primary, question_count: main, primary: true }, ...secondary.map((role, index) => ({
    role, question_count: Math.floor(remaining / secondary.length) + Number(index < remaining % secondary.length), primary: false,
  }))]
}
