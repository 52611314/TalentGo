<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, CirclePause, CirclePlay, FlaskConical, Lightbulb, RefreshCw, Send, ShieldCheck, SkipForward, Square } from '@lucide/vue'
import { ApiError, randomKey, request } from '../api/client'
import { useIdentityStore } from '../stores/identity'
import { useOperationStream } from '../composables/useOperationStream'
import { useSessionRecovery } from '../composables/useSessionRecovery'
import { MODE_LABELS, STATUS_LABELS } from '../types/session'

defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const route = useRoute()
const router = useRouter()
const recovery = useSessionRecovery()
const stream = useOperationStream()
const { session, messages, loading, error } = recovery
const { partial, phase, streamError, connected } = stream
const draft = ref('')
const sending = ref(false)
const actionError = ref('')
const uncertain = ref(false)
let scope = 0
type Pending = { path: string; method: string; body: Record<string, unknown>; key: string }
const pending = ref<Pending | null>(null)
const sid = computed(() => String(route.params.id || ''))
const storageKey = computed(() => `talentgo.request.${identity.activeId}.${sid.value}`)
const draftKey = computed(() => `talentgo.draft.${identity.activeId}.${sid.value}`)
const active = computed(() => !!session.value?.active_operation_id)
const busy = computed(() => sending.value || active.value || loading.value || uncertain.value)
const failed = computed(() => session.value?.latest_operation && ['failed', 'cancelled'].includes(session.value.latest_operation.status))
const canAnswer = computed(() => session.value?.status === 'interviewing' && !!session.value.current_question && !busy.value && !failed.value)

watch(draft, value => {
  if (identity.identity && sid.value) localStorage.setItem(draftKey.value, value)
})

async function refresh(attach = true) {
  const owner = identity.identity
  const ticket = scope
  if (!owner || !await recovery.load(sid.value, owner.token) || ticket !== scope) return
  if (session.value?.status === 'completed') {
    stream.stop()
    await router.replace(`/sessions/${sid.value}/report`)
    return
  }
  if (attach && session.value?.active_operation_id) {
    void stream.attach(session.value.active_operation_id, owner.token, () => refresh(false))
  }
}

watch(() => [sid.value, identity.identity?.user_id], async () => {
  scope++
  stream.stop()
  recovery.reset()
  actionError.value = ''
  sending.value = false
  pending.value = null
  uncertain.value = false
  if (!identity.identity) return
  try {
    pending.value = JSON.parse(sessionStorage.getItem(storageKey.value) || 'null')
    uncertain.value = !!pending.value
  } catch { sessionStorage.removeItem(storageKey.value) }
  draft.value = localStorage.getItem(draftKey.value) || ''
  await refresh()
}, { immediate: true })

async function perform(path: string, body: Record<string, unknown>, method = 'POST', reuse = false) {
  const owner = identity.identity
  if (!owner || sending.value) return
  const ticket = scope
  const key = storageKey.value
  if (!reuse) pending.value = { path, body, method, key: randomKey() }
  const mutation = pending.value
  if (!mutation) return
  sessionStorage.setItem(key, JSON.stringify(mutation))
  sending.value = true
  actionError.value = ''
  try {
    await request(mutation.path, { method: mutation.method, headers: { 'Idempotency-Key': mutation.key }, body: JSON.stringify(mutation.body) }, owner.token)
    sessionStorage.removeItem(key)
    if (ticket !== scope) return
    pending.value = null
    uncertain.value = false
    if (mutation.body.kind === 'answer' || mutation.body.kind === 'clarification') draft.value = ''
    await refresh()
  } catch (e) {
    if (ticket !== scope) return
    actionError.value = e instanceof Error ? e.message : '操作失败'
    uncertain.value = e instanceof ApiError && e.status === 0
    if (!uncertain.value) {
      pending.value = null
      sessionStorage.removeItem(key)
    }
    await refresh()
  } finally { if (ticket === scope) sending.value = false }
}

function action(name: string, extra: Record<string, unknown> = {}) {
  if (!session.value) return
  return perform(`/sessions/${sid.value}/actions`, { expected_version: session.value.version, action: name, ...extra })
}
function send(content = draft.value) {
  if (!session.value || !content.trim()) return
  return perform(`/sessions/${sid.value}/messages`, { expected_version: session.value.version,
    kind: session.value.status === 'clarifying' ? 'clarification' : 'answer', content,
    ...(session.value.status !== 'clarifying' ? { question_id: session.value.current_question?.id } : {}) })
}
function control(name: 'cancel' | 'retry') {
  const operation = session.value?.latest_operation
  if (operation) return perform(`/operations/${operation.id}/${name}`, {})
}
function finish() {
  if (window.confirm('结束本次练习并整理已有问答？尚未回答的题目不会伪造分数。')) void action('finish')
}
function confirmPressure() {
  if (session.value) return perform(`/sessions/${sid.value}`, { expected_version: session.value.version,
    config: { ...session.value.config, pressure_consent: true } }, 'PATCH')
}
onBeforeUnmount(() => { scope++; stream.stop(); recovery.reset() })
</script>

<template>
  <div class="interview-heading"><RouterLink to="/history" class="text-link"><ArrowLeft :size="15" />训练记录</RouterLink><span class="mock-badge"><FlaskConical :size="14" /> {{ !session ? '正在读取训练来源' : session.is_mock ? 'Mock · 不进行能力评分' : `${session.model_name} · 原文证据评分` }}</span></div>
  <section v-if="!identity.identity" class="card empty-profile"><h2>请先选择训练身份</h2><p>面试只对所属身份开放。</p><button class="button primary" @click="$emit('create-identity')">选择训练身份</button></section>
  <p v-else-if="error" class="error-banner" role="alert">{{ error }} <button @click="refresh()">重新读取</button></p>
  <p v-else-if="loading && !session" class="muted">正在恢复面试…</p>
  <div v-if="session" class="interview-layout">
    <section class="card conversation-card">
      <header class="conversation-header"><div><h1>{{ session.title }}</h1><p>{{ session.role === 'frontend' ? '前端开发' : session.role === 'backend' ? '后端开发' : '岗位待确认' }} · {{ session.mode ? MODE_LABELS[session.mode] : '类型待确认' }}</p></div><span class="subtle-tag">{{ STATUS_LABELS[session.status] }}</span></header>
      <div class="conversation-messages" aria-live="polite">
        <div class="conversation-intro"><ShieldCheck :size="16" /><p>回答先保存，再生成下一条消息。刷新不会自动重发。{{ session.is_mock ? '当前使用固定规则演示。' : '模型反馈仅供训练参考，缺少证据的维度不计分。' }}</p></div>
        <div v-for="message in messages" :key="message.id" class="conversation-message" :class="message.speaker">
          <span class="speaker-label">{{ message.speaker === 'user' ? '你' : message.speaker === 'system' ? '状态记录' : session.is_mock ? 'TalentGo · Mock' : 'TalentGo' }}<small v-if="message.kind === 'followup'">{{ session.is_mock ? '固定追问' : '针对性追问' }}</small><small v-if="message.kind === 'hint'">提示</small></span>
          <p>{{ message.content }}</p>
        </div>
        <div v-if="active" class="conversation-message assistant temporary"><span class="speaker-label">TalentGo · 生成中 <span class="pulse-dot"></span></span><p>{{ partial || phase || '正在准备下一条完整消息…' }}</p><small>临时内容，成功保存后才成为正式消息</small></div>
        <div v-if="session.status === 'clarifying' && !busy" class="clarification-options"><p>先确认你的方向：</p><div v-if="!session.role"><button @click="send('前端')">前端开发</button><button @click="send('后端')">后端开发</button></div><div v-if="!session.mode"><button @click="send('技术')">技术面试</button><button @click="send('行为')">行为面试</button><button @click="send('压力')">压力面试</button></div><button v-if="!messages.length" class="text-link" @click="action('clarify')">帮我确认需要补充什么</button></div>
        <div v-if="session.status === 'ready'" class="ready-panel"><Check :size="23" /><h2>目标已经确认，准备好了吗？</h2><p>共 {{ session.config.question_count }} 个主问题，每题最多追问 {{ session.config.max_followups }} 次。</p><div v-if="session.mode === 'pressure' && !session.config.pressure_consent" class="pressure-consent"><p>压力模式需要你确认强度。可随时降低、暂停或结束。</p><button class="button primary" :disabled="busy" @click="confirmPressure">同意当前强度并保存</button></div><button v-else class="button primary" :disabled="busy" @click="action('start')"><CirclePlay :size="17" />开始面试</button></div>
        <div v-if="session.status === 'paused'" class="ready-panel"><CirclePause :size="24" /><h2>休息一下，再继续。</h2><p>已保存的回答和问题会保留。</p><button class="button primary" :disabled="busy" @click="action('resume')">恢复练习</button></div>
        <p v-if="session.status === 'aborted'" class="mock-notice">本次配置已取消，没有生成训练成绩。<RouterLink to="/practice">重新配置</RouterLink></p>
      </div>
      <div v-if="failed" class="operation-warning" role="status"><strong>{{ session.latest_operation?.status === 'cancelled' ? '本次生成已停止' : '本次生成未完成' }}</strong><p>已保存的输入保留。重试原操作不会重复保存答案。{{ session.latest_operation?.error_code }}</p><button class="button secondary" :disabled="busy" @click="control('retry')"><RefreshCw :size="14" />重试原操作</button></div>
      <p v-if="actionError || streamError" class="error-banner" role="alert">{{ actionError || streamError }}<button @click="refresh()">刷新状态</button></p>
      <div v-if="uncertain" class="operation-warning"><strong>上次请求的结果尚未确认</strong><p>请使用原请求键重试，不要重新输入同一条答案。</p><button class="button secondary" :disabled="sending" @click="pending && perform(pending.path, pending.body, pending.method, true)">确认上次提交</button></div>
      <form v-if="['interviewing', 'clarifying'].includes(session.status)" class="answer-composer" @submit.prevent="send()"><label for="interview-answer">{{ session.status === 'clarifying' ? '补充你的目标' : '你的回答' }}</label><textarea id="interview-answer" v-model="draft" maxlength="8000" rows="4" :disabled="session.status === 'clarifying' ? busy : !canAnswer" placeholder="先说结论，再补充理由与例子。不确定的部分可以如实说明。"></textarea><div><small>{{ draft.length }} / 8000 · 草稿仅保存在当前浏览器</small><button class="button primary" :disabled="!draft.trim() || (session.status === 'clarifying' ? busy : !canAnswer)"><Send :size="15" />提交回答</button></div></form>
    </section>
    <aside class="interview-aside"><section class="card progress-card"><div class="eyebrow">ONE STEP AT A TIME</div><h3>这次练习</h3><div class="question-counter"><strong>{{ session.current_question?.ordinal || 0 }}</strong><span>/ {{ session.config.question_count }} 题</span></div><div class="progress-track"><span :style="{ width: `${session.coverage.asked / session.config.question_count * 100}%` }"></span></div><dl><div><dt>当前主题</dt><dd>{{ session.current_question?.topic || '等待开始' }}</dd></div><div><dt>实际作答</dt><dd>{{ session.coverage.answered }} 题</dd></div><div><dt>本题追问</dt><dd>{{ session.current_question?.followup_count || 0 }} / {{ session.config.max_followups }}</dd></div></dl><p class="field-help">{{ session.is_mock ? '短于 50 字可能触发演示追问，不判断回答优劣。' : '评分由五个维度构成，证据与缺口将在报告中展示。本题用过提示时会单独标记。' }}</p></section>
      <section class="card session-controls"><h3>练习控制</h3><template v-if="active"><p>{{ session.latest_operation?.cancel_requested ? '正在确认停止，请稍候…' : connected ? '正在接收生成进度' : '正在连接操作事件' }}</p><button class="button secondary full" :disabled="sending || session.latest_operation?.cancel_requested" @click="control('cancel')"><Square :size="14" />停止生成</button></template><template v-else><button v-if="session.status === 'interviewing'" :disabled="busy || !session.current_question || session.current_question.hint_used" @click="action('hint')"><Lightbulb :size="16" />给我提示</button><button v-if="session.status === 'interviewing'" :disabled="busy || !session.current_question" @click="action('skip')"><SkipForward :size="16" />跳过本题</button><button v-if="session.status === 'interviewing'" :disabled="busy" @click="action('pause')"><CirclePause :size="16" />暂停练习</button><button v-if="session.mode === 'pressure' && session.config.pressure_level > 1 && ['interviewing','paused'].includes(session.status)" :disabled="busy" @click="action('lower_pressure', { pressure_level: 1 })">降低压力强度</button><button v-if="['interviewing','paused'].includes(session.status)" :disabled="busy" @click="finish">结束并整理总结 <ArrowRight :size="15" /></button><button v-if="['clarifying','ready'].includes(session.status)" :disabled="busy" @click="action('abort')">取消本次配置</button></template></section>
    </aside>
  </div>
</template>
