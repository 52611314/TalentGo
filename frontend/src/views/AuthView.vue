<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check } from '@lucide/vue'
import { useIdentityStore } from '../stores/identity'
import { returnPath } from '../router/auth'
import { staggeredEntrance as vStaggeredEntrance } from '../directives/staggeredEntrance'

const route = useRoute()
const router = useRouter()
const store = useIdentityStore()
const registering = computed(() => route.path === '/register')
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const destination = computed(() => returnPath(route.query.redirect))
const alternate = computed(() => ({ path: registering.value ? '/login' : '/register', query: destination.value === '/' ? {} : { redirect: destination.value } }))
watch(registering, () => { password.value = ''; error.value = '' })
async function submit() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    await store.signIn(registering.value ? 'register' : 'login', username.value.trim(), password.value)
    password.value = ''
    await router.replace(destination.value)
  } catch (e) { error.value = e instanceof Error ? e.message : '暂时无法登录，请稍后重试' }
  finally { busy.value = false }
}
</script>

<template>
  <main :key="route.path" v-staggered-entrance class="auth-page">
    <section class="auth-story" aria-label="TalentGo 面试成长空间">
      <RouterLink to="/login" class="brand" aria-label="TalentGo 登录"><span class="brand-mark">T<span></span></span><span class="brand-word">Talent<span class="brand-light">Go</span><span class="brand-dot">.</span></span></RouterLink>
      <div class="auth-story-copy"><h2>把每一次准备，<br />变成向前的底气。</h2><p>找到你的方向，练习有分量的回答。<br />让成长有迹可循，让下一次机会更近一步。</p><div class="auth-benefits"><span><Check :size="16" />48 个岗位，按目标练习</span><span><Check :size="16" />真实问答，基于证据复盘</span><span><Check :size="16" />独立账号，持续积累进步</span></div></div>
      <p class="auth-story-footer">TalentGo · 你的面试成长空间</p>
    </section>
    <section class="auth-content">
      <div class="auth-panel card">
        <div class="eyebrow"><span></span> {{ registering ? 'START YOUR JOURNEY' : 'WELCOME BACK' }}</div>
        <h1>{{ registering ? '开启你的成长空间' : '欢迎回来' }}</h1>
        <p class="auth-subtitle">{{ registering ? '创建一个账号，保存属于你的练习与进步。' : '登录 TalentGo，继续为下一次机会做好准备。' }}</p>
        <form class="identity-form" @submit.prevent="submit">
          <fieldset :disabled="busy">
            <label for="account-username">账号</label><input id="account-username" v-model="username" minlength="3" maxlength="32" pattern="[A-Za-z0-9_]+" placeholder="3—32 位字母、数字或下划线" autocomplete="username" required />
            <label for="account-password">密码</label><input id="account-password" v-model="password" type="password" minlength="8" maxlength="128" placeholder="8—128 位密码" :autocomplete="registering ? 'new-password' : 'current-password'" required />
          </fieldset>
          <p class="field-help auth-account-note">账号与训练记录持久保存在数据库中。登录状态有效期为 7 天，到期后重新登录即可，账号和记录不会因此删除。</p>
          <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
          <button class="button primary full" :disabled="busy || !username.trim() || password.length < 8">{{ busy ? '请稍候…' : registering ? '注册并进入' : '登录' }}<ArrowRight :size="16" /></button>
        </form>
        <p class="auth-switch">{{ registering ? '已经有账号？' : '还没有账号？' }}<RouterLink v-if="!busy" :to="alternate">{{ registering ? '前往登录' : '注册账号' }}</RouterLink><span v-else>请稍候</span></p>
      </div>
      <p class="auth-copyright">每一步准备，都值得被记录。</p>
    </section>
  </main>
</template>
