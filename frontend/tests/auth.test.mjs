import assert from 'node:assert/strict'
import { after, beforeEach, test } from 'node:test'
import { createServer } from 'vite'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const { useIdentityStore } = await vite.ssrLoadModule('/src/stores/identity.ts')
const { returnPath, installAuthGuard } = await vite.ssrLoadModule('/src/router/auth.ts')
const originalFetch = globalThis.fetch
const originalStorage = globalThis.localStorage
after(async () => { globalThis.fetch = originalFetch; globalThis.localStorage = originalStorage; await vite.close() })
const account = { user_id: 'c6422818-c566-41ac-b8ad-7d3d20bd7490', username: 'student', display_name: 'student', token: 'test-token', expires_at: new Date(Date.now() + 86400000).toISOString() }
const profile = { user_id: account.user_id, version: 1, goals: 'saved goal', tech_stack: [] }
beforeEach(() => {
  setActivePinia(createPinia())
  const values = new Map()
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
  globalThis.fetch = async url => new Response(JSON.stringify({ data: String(url).includes('/auth/') ? { ...account, profile } : String(url).includes('/identity/me') ? account : profile }), { status: 200, headers: { 'Content-Type': 'application/json' } })
})
function router() {
  const page = { render: () => null }
  const r = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/login', component: page, meta: { authPage: true } },
    { path: '/register', component: page, meta: { authPage: true } },
    ...['/', '/profile', '/practice', '/history'].map(path => ({ path, component: page })),
  ] })
  installAuthGuard(r)
  return r
}
test('only local non-auth destinations are retained', () => {
  for (const value of ['https://evil.example', '//evil.example', '/\\evil', '/login?redirect=/profile', '/register/', null, ['/profile'], '/\nprofile']) assert.equal(returnPath(value), '/')
  assert.equal(returnPath('/practice?mode=pressure#form'), '/practice?mode=pressure#form')
})
test('anonymous deep links require login and preserve the destination', async () => {
  const r = router()
  await r.push('/practice?mode=pressure')
  assert.equal(r.currentRoute.value.path, '/login')
  assert.equal(r.currentRoute.value.query.redirect, '/practice?mode=pressure')
  await r.push('/register?redirect=/profile')
  assert.equal(r.currentRoute.value.path, '/register')
})
test('registered accounts enter the requested page; logout protects it again', async () => {
  const store = useIdentityStore()
  await store.initialize()
  await store.signIn('register', 'student', 'password')
  const r = router()
  await r.push('/login?redirect=/profile')
  assert.equal(r.currentRoute.value.path, '/profile')
  assert.equal(store.profile.goals, 'saved goal')
  globalThis.fetch = async () => new Response(null, { status: 204 })
  await store.logout()
  await r.push('/history')
  assert.equal(r.currentRoute.value.path, '/login')
})
test('refresh validates cached credentials once before deciding access', async () => {
  localStorage.setItem('talentgo.account.v2', JSON.stringify(account))
  let requests = 0
  const fetch = globalThis.fetch
  globalThis.fetch = async (...args) => { requests++; return fetch(...args) }
  const r = router()
  await r.push('/profile')
  assert.equal(r.currentRoute.value.path, '/profile')
  await r.push('/history')
  assert.equal(requests, 2)
})
test('expired or revoked cached credentials lead to login without deleting server data', async () => {
  localStorage.setItem('talentgo.account.v2', JSON.stringify(account))
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: 'UNAUTHORIZED', message: '请重新登录' } }), { status: 401 })
  const r = router()
  await r.push('/profile')
  assert.equal(r.currentRoute.value.path, '/login')
  assert.equal(localStorage.getItem('talentgo.account.v2'), null)
})
test('blocked browser storage does not invalidate a successful database login', async () => {
  globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }
  const store = useIdentityStore()
  await store.initialize()
  await store.signIn('login', 'student', 'password')
  assert.equal(store.identity.user_id, account.user_id)
  const r = router()
  await r.push('/profile')
  assert.equal(r.currentRoute.value.path, '/profile')
})
test('a session that expires while the app stays open goes back to login on navigation', async () => {
  const store = useIdentityStore()
  await store.initialize()
  await store.signIn('login', 'student', 'password')
  const r = router()
  await r.push('/profile')
  store.identity.expires_at = new Date(Date.now() - 1000).toISOString()
  await r.push('/history')
  assert.equal(r.currentRoute.value.path, '/login')
  assert.equal(r.currentRoute.value.query.redirect, '/history')
  assert.equal(store.identity, null)
})
