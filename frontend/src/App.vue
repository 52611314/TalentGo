<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElDialog, ElMessage } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/message/style/css'
import { ArrowUpRight, Brain, TrendingUp, BriefcaseBusiness, ChartNoAxesCombined, ChevronDown, CircleHelp, FileUser, LayoutDashboard, Plus, Sparkles, Terminal, X } from '@lucide/vue'
import { useIdentityStore } from './stores/identity'

const store = useIdentityStore()
const route = useRoute()
const dialog = ref(false)
const creating = ref(false)
const displayName = ref('')
const dialogError = ref('')
const initial = computed(() => store.identity?.display_name.slice(0, 1) || 'T')

async function create() {
  if (!displayName.value.trim() || creating.value) return
  creating.value = true
  dialogError.value = ''
  try {
    await store.create(displayName.value.trim())
    displayName.value = ''
    dialog.value = false
    ElMessage.success('训练身份已创建，档案已存入本地数据库')
  } catch (e) { dialogError.value = e instanceof Error ? e.message : '创建失败' }
  finally { creating.value = false }
}
onMounted(() => store.restore())
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink to="/" class="brand" aria-label="TalentGo 首页"><span class="brand-mark">T<span></span></span>Talent<span class="brand-light">Go</span><span class="brand-dot">.</span></RouterLink>
      <p class="workspace-label">PERSONAL WORKSPACE</p>
      <nav aria-label="主导航">
        <RouterLink to="/" class="nav-item" :class="{ active: route.path === '/' }"><LayoutDashboard :size="19" />工作台</RouterLink>
        <RouterLink to="/profile" class="nav-item" :class="{ active: route.path === '/profile' }"><FileUser :size="19" />训练档案<span class="nav-dot" v-if="!store.profile?.target_role"></span></RouterLink>
        <RouterLink to="/practice" class="nav-item" :class="{ active: route.path === '/practice' || route.path.startsWith('/sessions/') }"><BriefcaseBusiness :size="19" />面试练习<span class="nav-tag">M4</span></RouterLink>
        <RouterLink to="/history" class="nav-item" :class="{ active: route.path === '/history' }"><ChartNoAxesCombined :size="19" />训练记录</RouterLink>
        <RouterLink to="/memories" class="nav-item"><Brain :size="19" />训练记忆</RouterLink>
        <RouterLink to="/growth" class="nav-item"><TrendingUp :size="19" />复练与成长</RouterLink>
      </nav>
      <div class="sidebar-note"><div class="note-symbol"><Sparkles :size="18" /></div><strong>把准备，变成底气。</strong><p>从了解自己开始，<br />一步一步，走向理想 Offer。</p><RouterLink to="/profile">完善我的档案 <ArrowUpRight :size="15" /></RouterLink></div>
      <div class="sidebar-bottom"><span class="stage-dot"></span><span>M4 · 记忆与复练</span><span class="version">v0.4</span></div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb">我的空间 <span>/</span> <strong>{{ route.meta.title }}</strong></div><div class="topbar-actions"><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noopener" class="api-link"><Terminal :size="15" /> API 文档 <ArrowUpRight :size="13" /></a><button class="account" @click="dialog = true"><span class="avatar">{{ initial }}</span><span>{{ store.identity?.display_name || '访客空间' }}</span><ChevronDown :size="14" /></button></div></header>
      <main><RouterView @create-identity="dialog = true" /></main>
      <footer class="page-footer"><span>TalentGo · 为下一次机会，做好准备</span><span>M4 · 模型反馈仅供练习参考</span></footer>
    </div>
  </div>
  <ElDialog v-model="dialog" title="你的训练身份" width="460px" align-center :close-on-click-modal="false">
    <div v-if="store.identities.length" class="identity-list"><p class="muted">选择保存在此浏览器中的身份</p><button v-for="person in store.identities" :key="person.user_id" class="identity-option" :class="{ selected: person.user_id === store.activeId }" @click="store.select(person.user_id).then(() => dialog = false)"><span class="avatar">{{ person.display_name.slice(0, 1) }}</span><strong>{{ person.display_name }}</strong><span>{{ person.user_id === store.activeId ? '当前使用' : '切换' }}</span></button></div>
    <form @submit.prevent="create" class="identity-form"><label for="display-name">{{ store.identities.length ? '或创建新的训练身份' : '怎么称呼你？' }}</label><input id="display-name" v-model="displayName" maxlength="60" placeholder="输入一个喜欢的昵称" autocomplete="nickname" :disabled="creating" /><p class="field-help">无需邮箱与密码。身份凭证保存在当前浏览器，请勿在公共设备上使用；清除浏览器数据后无法找回。</p><p v-if="dialogError" class="error-text" role="alert">{{ dialogError }}</p><button class="button primary full" :disabled="!displayName.trim() || creating"><Plus :size="17" />{{ creating ? '正在创建…' : '创建训练身份' }}</button></form>
  </ElDialog>
</template>
