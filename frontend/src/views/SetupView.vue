<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import RolePicker from '../components/RolePicker.vue'
import { roleLabel, rolePlan } from '../data/roles'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Braces } from '@lucide/vue'
import { ApiError, randomKey, request } from '../api/client'
import { useIdentityStore } from '../stores/identity'
import type { InterviewMode, InterviewSession, ModelStatus, TargetRole } from '../types/session'

defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const router = useRouter()
const route = useRoute()
const busy = ref(false)
const error = ref('')
const uncertain = ref(false)
const models = ref<ModelStatus | null>(null)
const modelError = ref('')
let pending: { signature: string; key: string; body: string } | null = null
const pendingKey = computed(() => `talentgo.create-session.${identity.activeId}`)
let scope = 0
const form = reactive({ title: '我的模拟面试', source_task_id: undefined as string | undefined, provider: 'mock' as 'mock' | 'deepseek', role: null as TargetRole | null, mode: null as InterviewMode | null,
  config: { secondary_roles: [] as string[], question_count: 5, difficulty: 1, max_followups: 1, pressure_level: 1, pressure_consent: false } })
watch([() => identity.activeId, () => route.query.mode, () => route.query.task], async () => {
  const ticket = ++scope
  busy.value=false;error.value='';pending=null;uncertain.value=false
  const selectedMode=route.query.mode
  Object.assign(form,{title:'我的模拟面试',source_task_id:undefined,
    provider:models.value?.default_provider||'mock',role:identity.profile?.target_role||null,
    mode:['technical','behavioral','pressure'].includes(String(selectedMode))?selectedMode:null,
    config:{secondary_roles:[...(identity.profile?.secondary_roles || [])],question_count:5,difficulty:1,max_followups:1,pressure_level:1,pressure_consent:false}})
  const token=identity.identity?.token
  if(!token)return
  try {
    const saved=JSON.parse(sessionStorage.getItem(pendingKey.value)||'null')
    if(saved?.key && saved?.body){
      const body=JSON.parse(saved.body)
      pending=saved;Object.assign(form,body);uncertain.value=true
      return // Recover the original body; task lookup must never rewrite an uncertain submission.
    }
  } catch {sessionStorage.removeItem(pendingKey.value)}
  const task=route.query.task
  if(typeof task!=='string'||!task)return
  try {
    const result=await request<{id:string;role:TargetRole;mode:InterviewMode;topic:string}>(`/practice-tasks/${encodeURIComponent(task)}`,{},token)
    if(ticket!==scope)return
    form.source_task_id=result.id;form.config.secondary_roles=[];form.role=result.role;form.mode=result.mode;form.provider='deepseek'
    form.title=`针对复练 · ${result.topic}`;form.config.question_count=1
  }catch(e){if(ticket===scope)error.value=e instanceof Error?e.message:'读取来源任务失败'}
},{immediate:true})
watch(() => identity.profile, profile => {
  if(!form.role && !pending && !uncertain.value && !route.query.task) {
    form.role=profile?.target_role||null
    form.config.secondary_roles=[...(profile?.secondary_roles || [])]
  }
})
watch(() => identity.identity?.token, async token => {
  models.value=null;modelError.value=''
  if(!token)return
  try {
    const status=await request<ModelStatus>('/models/status',{},token)
    if(identity.identity?.token!==token)return
    models.value=status
    if(!pending && !form.source_task_id)form.provider=status.default_provider
  }catch{if(identity.identity?.token===token)modelError.value='模型状态读取失败，请刷新后选择真实模型。Mock 仍可使用。'}
},{immediate:true})
watch(() => form.config.secondary_roles?.length || 0, count => { if (count && form.config.question_count < count + 2 && !uncertain.value && !pending) form.config.question_count = count + 2 })
const allocation = computed(() => rolePlan(form.role, form.config.secondary_roles || [], form.config.question_count))
async function create() {
  if (!identity.identity || busy.value) return
  if (!pending && route.query.task && !form.source_task_id) { error.value = '来源任务尚未读取成功，请刷新后再创建复练'; return }
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
  <section class="page-heading"><div><div class="eyebrow"><span></span> MAKE ROOM FOR PRACTICE</div><h1>一次练习，从一个小目标开始。</h1><p>选好方向，也可以先留下不确定的地方，让我们一起确认。</p></div></section>
  <section v-if="!identity.identity" class="card empty-profile"><Braces :size="32" /><h2>登录账号，开始你的练习</h2><p>面试记录只对所属账号开放，刷新后也可以继续。</p><button class="button primary" @click="$emit('create-identity')">登录 / 注册 <ArrowRight :size="16" /></button></section>
  <div v-else class="setup-layout streamlined-layout">
    <form class="card profile-form" @submit.prevent="create">
      <div class="form-card-title"><span class="icon-box"><Braces :size="20" /></span><div><h2>配置这次练习</h2><p>选择岗位与面试类型，也可以保留不确定项，在开始前确认。</p></div></div>
      <p v-if="form.source_task_id" class="mock-notice">本次来源于已有复练任务：首题针对来源主题，实际完成有效评价后更新任务。</p>
      <fieldset :disabled="busy || uncertain">
        <div class="form-section"><label for="session-provider">训练来源</label><select id="session-provider" v-model="form.provider" :disabled="!!form.source_task_id"><option value="mock">Mock · 固定规则，不计分</option><option value="deepseek" :disabled="!models?.providers.find(p => p.id === 'deepseek')?.available">DeepSeek · {{ models?.providers.find(p => p.id === 'deepseek')?.model || '需配置密钥' }}</option></select><p class="field-help">{{ models?.providers.find(p => p.id === form.provider)?.description || '正在读取本地配置…' }}</p><p v-if="modelError" class="error-banner">{{ modelError }}</p></div>
        <div class="form-section"><label for="session-title">练习名称</label><input id="session-title" v-model="form.title" minlength="1" maxlength="120" required />
          <div class="two-fields"><div><label for="session-mode">面试类型</label><select id="session-mode" v-model="form.mode" :disabled="!!form.source_task_id"><option :value="null">还不确定，先确认</option><option value="technical">技术面试</option><option value="behavioral">行为面试</option><option value="pressure">压力面试</option></select></div></div>
        </div>
        <div class="form-section"><h3>选择目标岗位</h3><p class="field-help">选一个主岗位，也可以添加最多两个次选岗位。次选岗位题量少于主岗位。</p><RolePicker v-model="form.role" v-model:secondary-roles="form.config.secondary_roles" multiple :disabled="!!form.source_task_id || busy || uncertain" /><div v-if="allocation.length" class="role-allocation"><span v-for="item in allocation" :key="item.role">{{ item.primary ? '主岗位' : '次选' }} · {{ roleLabel(item.role) }} <strong>{{ item.question_count }} 题</strong></span></div></div>
        <div class="form-section"><div class="form-section-label"><span>02</span><h3>控制你的练习节奏</h3></div><div class="two-fields"><div><label for="question-count">总问题数量（1—10）</label><input id="question-count" type="number" v-model.number="form.config.question_count" :min="form.config.secondary_roles?.length ? form.config.secondary_roles.length + 2 : 1" max="10" required /></div><div><label for="followups">每题追问上限</label><select id="followups" v-model.number="form.config.max_followups"><option :value="0">不追问</option><option :value="1">最多 1 次</option><option :value="2">最多 2 次</option></select></div><div><label for="difficulty">起始难度</label><select id="difficulty" v-model.number="form.config.difficulty"><option :value="1">基础</option><option :value="2">进阶</option><option :value="3">深入</option></select></div></div></div>
        <div v-if="form.mode === 'pressure'" class="form-section"><label for="pressure-level">压力强度</label><select id="pressure-level" v-model.number="form.config.pressure_level"><option :value="1">温和</option><option :value="2">适中</option><option :value="3">较强</option></select><label class="memory-toggle"><input type="checkbox" v-model="form.config.pressure_consent" /><span><strong>我已了解并同意当前强度</strong><small>可以随时降低强度、暂停或结束。训练不作心理评价。</small></span></label></div>
      </fieldset>
      <p v-if="error || uncertain" class="error-banner" role="alert">{{ error || '上次创建结果未确认，请用原请求确认，避免重复建立练习。' }}</p>
      <div class="form-actions setup-actions"><button class="button primary" :disabled="busy || (form.mode === 'pressure' && !form.config.pressure_consent)">{{ busy ? '创建中…' : uncertain ? '确认上次创建' : '创建练习' }}<ArrowRight :size="16" /></button></div>
    </form>
  </div>
</template>
