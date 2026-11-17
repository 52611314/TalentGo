import type { Router } from 'vue-router'
import { useIdentityStore } from '../stores/identity'

export function returnPath(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || /[\\\u0000-\u0020]/.test(value)) return '/'
  const path = value.split(/[?#]/)[0]?.replace(/\/+$/, '')
  return path === '/login' || path === '/register' ? '/' : value
}

export function installAuthGuard(router: Router) {
  router.beforeEach(async to => {
    const store = useIdentityStore()
    await store.initialize()
    store.expireIfNeeded()
    if (to.meta.authPage) {
      if (store.identity) return returnPath(to.query.redirect)
    } else if (!store.identity) {
      return { path: '/login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
    }
  })
}
