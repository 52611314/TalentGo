<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Braces, FlaskConical, ShieldCheck } from '@lucide/vue'
import { ApiError, randomKey, request } from '../api/client'
import { useIdentityStore } from '../stores/identity'
import type { InterviewMode, InterviewSession, TargetRole } from '../types/session'

defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const router = useRouter()
const route = useRoute()
const busy = ref(false)
const error = ref('')
const uncertain = ref(false)
let pending: { signature: string; key: string; body: string } | null = null
const pendingKey = computed(() => `talentgo.create-session.${identity.activeId}`)
let scope = 0
const form = reactive({ title: '我的模拟面试', role: null as TargetRole | null, mode: null as InterviewMode | null,
  config: { question_count: 3, difficulty: 1, max_followups: 1, pressure_level: 1, pressure_consent: false } })
watch(() => [identity.activeId, identity.profile, route.query.mode], () => {
  scope++
  busy.value = false
  form.role = identity.profile?.target_role || null
  const mode = route.query.mode
  form.mode = mode === 'technical' || mode === 'behavioral' || mode === 'pressure' ? mode : null
  pending = null
  uncertain.value = false
  if (identity.identity) {
    try {
      const saved = JSON.parse(sessionStorage.getItem(pendingKey.value) || 'null')
      if (saved?.key && saved?.body) {
        pending = saved
        Object.assign(form, JSON.parse(saved.body))
        uncertain.value = true
      }
    } catch { sessionStorage.removeItem(pendingKey.value) }
  }
}, { immediate: true })
const needsClarification = computed(() => !form.role || !form.mode)
async function create() {
  if (!identity.identity || busy.value) return
  busy.value = true
  const ticket = scope
  error.value = ''
  const owner = identity.identity.user_id
  const token = identity.identity.token
  const storage = pendingKey.value
  const body = JSON.stringify(form)
  const signature = owner + body
  if (pending?.signature !== signature) pending = { signature, key: randomKey(), body }
  sessionStorage.setItem(storage, JSON.stringify(pending))
  try {
    const result = await request<InterviewSession>('/sessions', { method: 'POST',
      headers: { 'Idempotency-Key': pending!.key }, body }, token)
    sessionStorage.removeItem(storage)
    if (ticket !== scope) return
    pending = null
    uncertain.value = false
    if (identity.identity?.user_id === owner) await router.push(`/sessions/${result.id}`)
  } catch (e) {
    if (ticket !== scope) return
    error.value = e instanceof Error ? e.message : '创建失败；原配置可直接重试'
    uncertain.value = e instanceof ApiError && e.status === 0
    if (!uncertain.value) { pending = null; sessionStorage.removeItem(storage) }
  }
  finally { if (ticket === scope) busy.value = false }
}
</script>

<template>
  <section class="page-heading"><div><div class="eyebrow"><span></span> MAKE ROOM FOR PRACTICE</div><h1>一次练习，从一个小目标开始。</h1><p>选好方向，也可以先留下不确定的地方，让我们一起确认。</p></div><span class="mock-badge"><FlaskConical :size="14" /> M2 · 固定规则 Mock</span></section>
  <section v-if="!identity.identity" class="card empty-profile"><Braces :size="32" /><h2>先为你的练习建立身份</h2><p>面试记录只对当前身份开放，刷新后也可以继续。</p><button class="button primary" @click="$emit('create-identity')">创建训练身份 <ArrowRight :size="16" /></button></section>
  <div v-else class="setup-layout">
    <form class="card profile-form" @submit.prevent="create">
      <div class="form-card-title"><span class="icon-box"><Braces :size="20" /></span><div><h2>配置这次练习</h2><p>不确定岗位或类型时，选择「先确认」进入澄清。</p></div></div>
      <fieldset :disabled="busy || uncertain">
        <div class="form-section"><label for="session-title">练习名称</label><input id="session-title" v-model="form.title" minlength="1" maxlength="120" required />
          <div class="two-fields"><div><label for="session-role">目标岗位</label><select id="session-role" v-model="form.role"><option :value="null">还不确定，先确认</option><option value="frontend">前端开发</option><option value="backend">后端开发</option></select></div><div><label for="session-mode">面试类型</label><select id="session-mode" v-model="form.mode"><option :value="null">还不确定，先确认</option><option value="technical">技术面试</option><option value="behavioral">行为面试</option><option value="pressure">压力面试</option></select></div></div>
        </div>
        <div class="form-section"><div class="form-section-label"><span>02</span><h3>控制你的练习节奏</h3></div><div class="two-fields"><div><label for="question-count">主问题数量（1—10）</label><input id="question-count" type="number" v-model.number="form.config.question_count" min="1" max="10" required /></div><div><label for="followups">每题追问上限</label><select id="followups" v-model.number="form.config.max_followups"><option :value="0">不追问</option><option :value="1">最多 1 次</option><option :value="2">最多 2 次</option></select></div><div><label for="difficulty">起始难度</label><select id="difficulty" v-model.number="form.config.difficulty"><option :value="1">基础</option><option :value="2">进阶</option><option :value="3">深入</option></select></div></div></div>
        <div v-if="form.mode === 'pressure'" class="form-section"><label for="pressure-level">压力强度</label><select id="pressure-level" v-model.number="form.config.pressure_level"><option :value="1">温和</option><option :value="2">适中</option><option :value="3">较强</option></select><label class="memory-toggle"><input type="checkbox" v-model="form.config.pressure_consent" /><span><strong>我已了解并同意当前强度</strong><small>可以随时降低强度、暂停或结束。Mock 仅演示问答，不作心理评价。</small></span></label></div>
      </fieldset>
      <p class="mock-notice"><FlaskConical :size="16" />当前使用固定题目与演示规则，未接入大模型，也不评估能力分数。</p>
      <p v-if="error || uncertain" class="error-banner" role="alert">{{ error || '上次创建结果未确认，请用原请求确认，避免重复建立练习。' }}</p>
      <div class="form-actions"><span class="save-state">{{ needsClarification ? '将先确认缺少的目标' : '创建后可确认并开始练习' }}</span><button class="button primary" :disabled="busy || (form.mode === 'pressure' && !form.config.pressure_consent)">{{ busy ? '创建中…' : uncertain ? '确认上次创建' : '创建练习' }}<ArrowRight :size="16" /></button></div>
    </form>
    <aside class="card setup-note"><ShieldCheck :size="24" /><h3>按你的节奏来。</h3><p>回答会先保存，再生成下一条消息。刷新不会自动重发答案。</p><p>短于 50 字的回答可能触发固定追问；这只是 Mock 流程规则，不代表回答质量。</p><p>开始后冻结本次配置与画像快照，避免训练中途悄悄改变目标。</p></aside>
  </div>
</template>
