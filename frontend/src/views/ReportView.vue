<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowRight, CheckCheck, FlaskConical } from '@lucide/vue'
import { getReport, getTrace, getExport } from '../api/sessions'
import { request } from '../api/client'
import { useIdentityStore } from '../stores/identity'
import { DIMENSION_LABELS, type InterviewReport, type SkillTrace } from '../types/session'
defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const route = useRoute()
const report = ref<InterviewReport | null>(null)
const error = ref('')
const traces = ref<SkillTrace[]>([])
const traceError = ref('')
const traceLoading = ref(false), exporting = ref(false), exportError = ref('')
const memoryUsages = ref<{id:string;memory_id:string;memory_version:number;memory_revision:number;phase:string;reason:string;still_exists:boolean}[]>([])
let epoch = 0
watch([() => route.params.id, () => identity.activeId], async () => {
  const ticket = ++epoch
  report.value = null
  error.value = ''
  traces.value = []
  traceError.value = ''
  memoryUsages.value = []
  traceLoading.value = false; exporting.value = false; exportError.value = ''
  if (!identity.identity) return
  const token = identity.identity.token
  const id = String(route.params.id)
  try {
    const result = await getReport(id, token)
    if (ticket !== epoch) return
    report.value = result
    await nextTick()
    if (ticket === epoch && route.hash) document.getElementById(route.hash.slice(1))?.scrollIntoView({ block: 'start' })
    if (!result.is_mock) {
      traceLoading.value = true
      try {
        const trace = await getTrace(id, token)
        if (ticket === epoch) traces.value = trace.items
        const usage = await request<{items:typeof memoryUsages.value}>(`/sessions/${id}/memory-usages`, {}, token)
        if (ticket === epoch) memoryUsages.value = usage.items
      } catch { if (ticket === epoch) traceError.value = '执行记录暂未读取成功，可刷新页面重试。' }
      finally { if (ticket === epoch) traceLoading.value = false }
    }
  } catch (e) { if (ticket === epoch) error.value = e instanceof Error ? e.message : '读取总结失败' }
}, { immediate: true })

async function download(format: 'markdown'|'json') {
  const token=identity.identity?.token, id=String(route.params.id), ticket=epoch
  if (!token || exporting.value) return
  exporting.value=true;exportError.value=''
  try {
    const blob=await getExport(id,format,token)
    if(ticket!==epoch)return
    const url=URL.createObjectURL(blob), link=document.createElement('a')
    link.href=url;link.download=`talentgo-${id}.${format==='json'?'json':'md'}`
    document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)
  } catch(e) { if(ticket===epoch)exportError.value=e instanceof Error?e.message:'导出失败' }
  finally { if(ticket===epoch)exporting.value=false }
}
</script>

<template>
  <RouterLink to="/history" class="text-link"><ArrowLeft :size="15" />返回训练记录</RouterLink>
  <section class="page-heading report-heading"><div><div class="eyebrow"><span></span> A PRACTICE WORTH KEEPING</div><h1>这一次练习，已经保存。</h1><p>先回顾真实发生的问答，再为下一次准备留一点空间。</p></div><span class="mock-badge"><FlaskConical :size="14" /> {{ report?.is_mock === false ? '模型反馈 · 仅供训练参考' : 'Mock 记录 · 非能力评价' }}</span></section>
  <section v-if="!identity.identity" class="card empty-profile"><h2>请先选择所属身份</h2><button class="button primary" @click="$emit('create-identity')">选择训练身份</button></section>
  <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
  <section v-if="report && report.status !== 'ready'" class="card empty-profile"><h2>总结尚未就绪</h2><p>请回到面试室查看操作状态；失败时重试原操作。</p><RouterLink :to="`/sessions/${route.params.id}`" class="button primary">返回面试室</RouterLink></section>
  <template v-if="report?.status === 'ready'">
      <section v-if="!report.is_mock" class="card score-overview"><div><div class="eyebrow">EVIDENCE BEFORE NUMBERS</div><h2>本场训练反馈</h2><div class="total-score">{{ report.total_score ?? '—' }}<small> / 100</small></div><p>有效计分 {{ report.coverage.scored }} / 计划 {{ report.coverage.planned }} 题</p><p class="field-help">有效主问题最终成绩取平均；跳过、未到达及未评题不计入。空缺维度按剩余权重归一。rubric-1.1 起至少一个内容维度可评才计总分，仅切题和表达不足以代表内容能力。</p></div><div class="dimension-list"><div v-for="(label, key) in DIMENSION_LABELS" :key="key"><div class="dimension-title"><strong>{{ label }}</strong><span>{{ report.dimension_scores?.[key] ?? '材料不足' }}{{ report.dimension_scores?.[key] != null ? ' / 5' : '' }} · 权重 {{ report.weights?.[key] }}%</span></div><div class="progress-track"><span :style="{width: `${(report.dimension_scores?.[key] || 0) * 20}%`}"></span></div></div></div></section>
    <section class="card report-summary"><span class="report-check"><CheckCheck :size="28" /></span><div><h2>完成一场练习，就是向前一步。</h2><p>{{ report.summary }}</p></div></section>
    <div class="coverage-grid"><section class="card" v-for="item in [{ label: '计划主问题', count: report.coverage.planned }, { label: '实际回答', count: report.coverage.answered }, { label: '已跳过', count: report.coverage.skipped }, { label: '尚未到达', count: report.coverage.not_reached }]" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.count }}<small>题</small></strong></section></div>
    <div v-if="report.is_mock" class="mock-notice"><FlaskConical :size="18" /><span>当前不提供总分或维度分。固定追问不代表回答质量，Mock 记录不能作为真实模型效果或真实用户测试。</span></div>
    <template v-else>
      <p class="mock-notice">反馈来自 {{ report.model_name }} · {{ report.prompt_version }} · {{ report.rubric_version }}。模型判断可能存在误差；评分不代表录用概率，不核实经历或诊断心理状态。</p>
      <div class="review-grid"><section v-for="group in [{title: '表现亮点', items: report.strengths}, {title: '待补充之处', items: report.gaps}, {title: '下一次怎么练', items: report.recommendations}]" :key="group.title" class="card"><h3>{{ group.title }}</h3><p v-if="!group.items?.length" class="muted">暂无足够依据</p><div v-for="(item, index) in group.items" :key="index" class="review-item"><p>{{ item.text }}</p><a v-for="qid in item.question_ids" :key="qid" :href="`#question-${qid}`" class="text-link">查看对应题目</a></div></section></div>
      <section class="card question-evaluation" v-for="q in report.question_evaluations" :key="q.id" :id="`question-${q.question_id}`"><div class="section-heading"><h2>第 {{ q.ordinal }} 题 · {{ q.topic }}</h2><strong>{{ q.question_score ?? '未计分' }}{{ q.question_score != null ? ' / 100' : '' }}</strong></div><p class="question-text">{{ q.question }}</p><span v-if="q.hint_used" class="subtle-tag">本题使用过提示</span><details v-for="(d, key) in q.dimensions" :key="key" class="evidence-dimension"><summary>{{ DIMENSION_LABELS[key] }} · {{ d.score ?? '材料不足' }}{{ d.score != null ? ' / 5' : '' }}</summary><p>{{ d.reason }}</p><blockquote v-for="(e, index) in d.evidence" :key="index"><p>“{{ e.quote }}”</p><a :href="`#message-${e.message_id}`">定位用户原文</a></blockquote></details><p v-if="q.missing_points.length"><strong>缺口：</strong>{{ q.missing_points.join('；') }}</p><p><strong>练习建议：</strong>{{ q.suggestion }}</p></section>
      <p class="mock-notice"><RouterLink to="/growth" class="text-link">查看来源复练任务与分组评分记录 →</RouterLink></p>
      <details class="card trace-panel"><summary>查看记忆注入来源（{{ traceLoading ? '读取中' : traceError ? '读取失败' : memoryUsages.length }}）</summary><p v-if="!traceLoading && !traceError && !memoryUsages.length" class="field-help">本场没有注入已确认记忆。</p><div v-for="u in memoryUsages" :key="u.id" class="trace-row"><strong>{{u.phase}} · {{u.reason}}</strong><span>记忆 {{u.memory_id}} · v{{u.memory_version}} · 当时记忆版本 {{u.memory_revision}} · {{u.still_exists?'当前仍存在':'已删除，轨迹仅保留编号'}}</span></div></details>
      <details class="card trace-panel"><summary>查看 Skill 执行记录（{{ traceLoading ? '读取中' : traceError ? '读取失败' : traces.length }}）</summary><p class="field-help">仅记录阶段、版本、用量与错误，不展示内部推理。未返回用量时显示「未知」。</p><p v-if="traceError" class="error-banner">{{ traceError }}</p><div v-for="t in traces" :key="t.id" class="trace-row"><strong>{{ t.skill_key }} · {{ t.phase }} · {{ t.status }}</strong><span>v{{ t.skill_version }} · 操作第 {{ t.attempt_no }} 次 · 模型请求 {{ t.usage.attempts ?? '未知' }} 次</span><span>输入 {{ t.usage.input_tokens ?? '未知' }} / 输出 {{ t.usage.output_tokens ?? '未知' }} tokens · {{ t.usage.latency_ms ?? '未知' }} ms {{ t.error_code }}</span></div></details>
    </template>
    <section class="card report-transcript"><div class="section-heading"><h2>本次问答记录</h2><span class="muted">完整正式消息，按实际顺序保存</span></div><div v-for="message in report.messages" :key="message.id" :id="`message-${message.id}`" class="transcript-item" :class="message.speaker"><span>{{ message.speaker === 'user' ? '你' : message.speaker === 'system' ? '状态' : report.is_mock ? 'TalentGo · Mock' : 'TalentGo' }}</span><p>{{ message.content }}</p></div></section>
    <p v-if="exportError" class="error-banner" role="alert">{{exportError}}</p>
    <div class="report-actions"><button class="button secondary" :disabled="exporting" @click="download('markdown')">导出 Markdown</button><button class="button secondary" :disabled="exporting" @click="download('json')">导出 JSON</button><RouterLink to="/history" class="button secondary">回顾训练记录</RouterLink><RouterLink to="/practice" class="button primary">再准备一次 <ArrowRight :size="16" /></RouterLink></div>
  </template>
</template>

<style scoped>
.score-overview{display:grid;grid-template-columns:1fr 1.4fr;gap:40px;padding:30px;margin:24px 0}.total-score{font-size:60px;font-weight:700;color:var(--primary,#7864ad);line-height:1.3}.total-score small{font-size:18px;color:#85818f}.dimension-list{display:grid;gap:20px;align-content:center}.dimension-title{display:flex;justify-content:space-between;gap:12px;font-size:13px;margin-bottom:7px}.dimension-title span{color:#777180}.review-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:22px 0}.review-grid .card{padding:24px}.review-item{padding:10px 0;border-bottom:1px solid #ece9f1}.review-item p{line-height:1.8;margin:0 0 8px}.question-evaluation{padding:28px;margin:20px 0;scroll-margin-top:20px}.question-text{line-height:1.9}.evidence-dimension{padding:14px 0;border-bottom:1px solid #ece9f1}.evidence-dimension summary,.trace-panel summary{cursor:pointer;font-weight:600}.evidence-dimension p{line-height:1.8}blockquote{margin:12px 0;padding:12px 20px;background:#f7f5fa;border-left:3px solid #a59ac4}blockquote a{font-size:12px;color:#71608b}.trace-panel{padding:24px;margin:22px 0}.trace-row{display:grid;gap:6px;padding:14px 0;border-top:1px solid #ece9f1;font-size:13px}.trace-row span{color:#777180}.transcript-item{scroll-margin-top:20px}.transcript-item:target{outline:2px solid #a59ac4;border-radius:8px}@media(max-width:800px){.score-overview,.review-grid{grid-template-columns:1fr}.dimension-title{flex-wrap:wrap}.score-overview{padding:20px;gap:20px}}
</style>
