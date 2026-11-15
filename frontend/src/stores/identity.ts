import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authenticate, getIdentity, logout as revokeSession } from '../api/identity'
import { getProfile, saveProfile } from '../api/profile'
import { ApiError, randomKey } from '../api/client'
import type { Identity } from '../types/api'
import type { Profile, ProfileInput } from '../types/session'

const STORAGE = 'talentgo.account.v2'

export const useIdentityStore = defineStore('identity', () => {
  const identity = ref<Identity | null>(null)
  const activeId = computed(() => identity.value?.user_id || '')
  const profile = ref<Profile | null>(null)
  const loading = ref(false)
  const error = ref('')
  let generation = 0
  let pending: { signature: string; key: string } | null = null
  const persist = () => identity.value ? localStorage.setItem(STORAGE, JSON.stringify(identity.value)) : localStorage.removeItem(STORAGE)

  function clear() {
    ++generation
    identity.value = null; profile.value = null; loading.value = false; pending = null
    persist()
  }
  async function refresh() {
    const current = identity.value
    const ticket = ++generation
    profile.value = null; error.value = ''
    if (!current) return
    loading.value = true
    try {
      const [me, result] = await Promise.all([getIdentity(current.token), getProfile(current.token)])
      if (ticket !== generation) return
      Object.assign(current, me); profile.value = result; persist()
    } catch (e) {
      if (ticket !== generation) return
      if (e instanceof ApiError && e.status === 401) clear()
      error.value = e instanceof Error ? e.message : '资料加载失败'
    } finally { if (ticket === generation) loading.value = false }
  }
  async function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE) || 'null')
      if (saved && typeof saved.user_id === 'string' && typeof saved.username === 'string' && typeof saved.token === 'string' && typeof saved.display_name === 'string' && Date.parse(saved.expires_at) > Date.now()) identity.value = saved
      else localStorage.removeItem(STORAGE)
    } catch { localStorage.removeItem(STORAGE) }
    await refresh()
  }
  async function signIn(mode: 'login' | 'register', username: string, password: string) {
    const result = await authenticate(mode, username, password)
    ++generation
    const { profile: loadedProfile, ...account } = result
    identity.value = account; profile.value = loadedProfile; error.value = ''; pending = null; loading.value = false
    persist()
  }
  async function logout() {
    if (identity.value) {
      try { await revokeSession(identity.value.token) }
      catch (e) { if (!(e instanceof ApiError && e.status === 401)) throw e }
    }
    clear(); error.value = ''
  }
  async function save(fields: ProfileInput) {
    const current = identity.value, snapshot = profile.value
    if (!current || !snapshot) throw new Error('请先登录并加载资料')
    const ticket = generation
    const signature = JSON.stringify([current.user_id, snapshot.version, fields])
    if (pending?.signature !== signature) pending = { signature, key: randomKey() }
    const result = await saveProfile(current.token, fields, snapshot.version, pending!.key)
    if (ticket === generation) { profile.value = result; pending = null }
  }
  return { activeId, identity, profile, loading, error, restore, refresh, signIn, logout, save }
})
