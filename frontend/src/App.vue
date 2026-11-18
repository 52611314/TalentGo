<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElDialog, ElMessage } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/message/style/css'
import { ArrowUpRight, Brain, TrendingUp, BriefcaseBusiness, ChartNoAxesCombined, ChevronDown, FileUser, LayoutDashboard, PanelLeftClose, PanelLeftOpen, Sparkles } from '@lucide/vue'
import { useIdentityStore } from './stores/identity'
import { loadRoles } from './data/roles'

const store = useIdentityStore()
const route = useRoute()
const dialog = ref(false)
const creating = ref(false)
const dialogError = ref('')
const router = useRouter()
const sidebarKey = 'talentgo.sidebar.collapsed'
const sidebarCollapsed = ref((() => {
  try { return localStorage.getItem(sidebarKey) === 'true' } catch { return false }
})())
watch(sidebarCollapsed, value => {
  try { localStorage.setItem(sidebarKey, String(value)) } catch { /* The layout still works when storage is unavailable. */ }
})
const navigation = [
  { to: '/', label: '工作台', icon: LayoutDashboard },
  { to: '/profile', label: '训练档案', icon: FileUser },
  { to: '/practice', label: '面试练习', icon: BriefcaseBusiness },
  { to: '/history', label: '训练记录', icon: ChartNoAxesCombined },
  { to: '/memories', label: '个人偏好', icon: Brain },
  { to: '/growth', label: '专项练习', icon: TrendingUp },
]
const activeNavigation = computed(() => route.path.startsWith('/sessions/') ? '/practice' : route.path)
const initial = computed(() => store.identity?.display_name.slice(0, 1) || 'T')
async function logout() {
  creating.value = true; dialogError.value = ''
  try { await store.logout(); dialog.value = false; await router.replace('/login'); ElMessage.success('已退出登录') }
  catch (e) { dialogError.value = e instanceof Error ? e.message : '退出失败，请重试' }
  finally { creating.value = false }
}
watch(dialog, () => { dialogError.value = '' })
watch(() => store.identity, account => {
  if (store.initialized && !account && !route.meta.authPage) void router.replace({ path: '/login', query: { redirect: route.fullPath } })
})
function openLogin() { void router.push({ path: '/login', query: { redirect: route.fullPath } }) }
onMounted(() => { void loadRoles().catch(() => {}) })
</script>

<template>
  <RouterView v-if="route.meta.authPage" />
  <div v-else class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside id="workspace-sidebar" class="sidebar" aria-label="工作空间侧边栏">
      <RouterLink to="/" class="brand" aria-label="TalentGo 首页" title="TalentGo 首页"><span class="brand-mark">T<span></span></span><span class="brand-word">Talent<span class="brand-light">Go</span><span class="brand-dot">.</span></span></RouterLink>
      <p class="workspace-label">PERSONAL WORKSPACE</p>
      <nav aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" class="nav-item" :class="{ active: activeNavigation === item.to }" :aria-label="item.label" :aria-current="activeNavigation === item.to ? 'page' : undefined" :title="sidebarCollapsed ? item.label : undefined"><component :is="item.icon" :size="19" /><span class="nav-label">{{ item.label }}</span><span class="nav-dot" v-if="item.to === '/profile' && !store.profile?.target_role"></span></RouterLink>
      </nav>
      <div class="sidebar-note" :inert="sidebarCollapsed" :aria-hidden="sidebarCollapsed"><div class="note-symbol"><Sparkles :size="18" /></div><strong>把准备，变成底气。</strong><p>从了解自己开始，<br />一步一步，走向理想 Offer。</p><RouterLink to="/profile">完善我的档案 <ArrowUpRight :size="15" /></RouterLink></div>
      <div class="sidebar-bottom"><span class="stage-dot"></span><span class="sidebar-bottom-label">准备，从这里开始</span></div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><div class="topbar-leading"><button class="sidebar-toggle" type="button" :aria-label="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'" :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'" :aria-expanded="!sidebarCollapsed" aria-controls="workspace-sidebar" @click="sidebarCollapsed = !sidebarCollapsed"><component :is="sidebarCollapsed ? PanelLeftOpen : PanelLeftClose" :size="19" /></button><div class="breadcrumb">我的空间 <span>/</span> <strong>{{ route.meta.title }}</strong></div></div><div class="topbar-actions"><button class="account" @click="dialog = true"><span class="avatar">{{ initial }}</span><span>{{ store.identity?.display_name || '登录 / 注册' }}</span><ChevronDown :size="14" /></button></div></header>
      <main id="main-content"><RouterView v-slot="{ Component, route: viewRoute }"><Transition name="page" mode="out-in" appear><div :key="viewRoute.path" class="page-view"><component :is="Component" @create-identity="openLogin" /></div></Transition></RouterView></main>
      <footer class="page-footer"><span>TalentGo · 为下一次机会，做好准备</span></footer>
    </div>
  </div>
  <ElDialog v-if="!route.meta.authPage" v-model="dialog" title="我的账号" width="460px" align-center :close-on-click-modal="false" :close-on-press-escape="!creating" :show-close="!creating">
    <div v-if="store.identity" class="identity-form">
      <p>当前账号：<strong>{{ store.identity.username }}</strong></p>
      <p class="field-help">退出后可使用账号和密码重新登录，继续查看自己的档案与面试记录。</p>
      <p v-if="dialogError" class="error-text" role="alert">{{ dialogError }}</p>
      <button class="button secondary full" :disabled="creating" @click="logout">{{ creating ? '正在退出…' : '退出登录' }}</button>
    </div>
  </ElDialog>
</template>
