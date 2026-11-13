import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createIdentity, getIdentity } from '../api/identity'
import { getProfile, saveProfile } from '../api/profile'
import { randomKey } from '../api/client'
import type { Identity } from '../types/api'
import type { Profile, ProfileInput } from '../types/session'

const STORAGE = 'talentgo.identities.v1'

export const useIdentityStore = defineStore('identity', () => {
  const identities = ref<Identity[]>([])
  const activeId = ref('')
  const profile = ref<Profile | null>(null)
  const loading = ref(false)
  const error = ref('')
  const identity = computed(() => identities.value.find(x => x.user_id === activeId.value) || null)
  const persist = () => localStorage.setItem(STORAGE, JSON.stringify({ identities: identities.value, activeId: activeId.value }))
  let generation = 0

  async function refresh() {
    const current = identity.value
    const ticket = ++generation
    profile.value = null
    error.value = ''
    if (!current) return
    loading.value = true
    try {
      const [me, result] = await Promise.all([getIdentity(current.token), getProfile(current.token)])
      if (ticket !== generation) return
      current.display_name = me.display_name
      profile.value = result
      persist()
    } catch (e) {
      if (ticket === generation) error.value = e instanceof Error ? e.message : '资料加载失败'
    } finally { if (ticket === generation) loading.value = false }
  }

  async function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE) || '{}')
      identities.value = Array.isArray(saved.identities) ? saved.identities.filter((x: Identity) =>
        typeof x?.user_id === 'string' && typeof x?.display_name === 'string' && typeof x?.token === 'string') : []
      activeId.value = typeof saved.activeId === 'string' ? saved.activeId : ''
    } catch { error.value = '本机身份数据无法读取，请重新创建身份' }
    await refresh()
  }

  async function create(name: string) {
    const result = await createIdentity(name)
    ++generation
    identities.value.push({ user_id: result.user_id, display_name: result.display_name, token: result.token })
    activeId.value = result.user_id
    profile.value = result.profile
    error.value = ''
    persist()
  }

  async function select(id: string) { activeId.value = id; persist(); await refresh() }

  // Reuse the request key for an uncertain network retry of unchanged content.
  let pending: { signature: string; key: string } | null = null
  async function save(fields: ProfileInput) {
    const current = identity.value
    const snapshot = profile.value
    if (!current || !snapshot) throw new Error('请先加载训练身份与资料')
    const ticket = generation
    const signature = JSON.stringify([current.user_id, snapshot.version, fields])
    if (pending?.signature !== signature) pending = { signature, key: randomKey() }
    const result = await saveProfile(current.token, fields, snapshot.version, pending!.key)
    if (ticket === generation) profile.value = result
    pending = null
  }

  return { identities, activeId, identity, profile, loading, error, restore, refresh, create, select, save }
})
