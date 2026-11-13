<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowRight, CheckCheck, FlaskConical } from '@lucide/vue'
import { getReport } from '../api/sessions'
import { useIdentityStore } from '../stores/identity'
import type { MockReport } from '../types/session'
defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const route = useRoute()
const report = ref<MockReport | null>(null)
const error = ref('')
let epoch = 0
watch(() => [route.params.id, identity.activeId], async () => {
  const ticket = ++epoch
  report.value = null
  error.value = ''
  if (!identity.identity) return
  try {
    const result = await getReport(String(route.params.id), identity.identity.token)
    if (ticket === epoch) report.value = result
  } catch (e) { if (ticket === epoch) error.value = e instanceof Error ? e.message : '读取总结失败' }
}, { immediate: true })
</script>

<template>
  <RouterLink to="/history" class="text-link"><ArrowLeft :size="15" />返回训练记录</RouterLink>
  <section class="page-heading report-heading"><div><div class="eyebrow"><span></span> A PRACTICE WORTH KEEPING</div><h1>这一次练习，已经保存。</h1><p>先回顾真实发生的问答，再为下一次准备留一点空间。</p></div><span class="mock-badge"><FlaskConical :size="14" /> Mock 记录 · 非能力评价</span></section>
  <section v-if="!identity.identity" class="card empty-profile"><h2>请先选择所属身份</h2><button class="button primary" @click="$emit('create-identity')">选择训练身份</button></section>
  <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
  <section v-if="report && report.status !== 'ready'" class="card empty-profile"><h2>总结尚未就绪</h2><p>请回到面试室查看操作状态；失败时重试原操作。</p><RouterLink :to="`/sessions/${route.params.id}`" class="button primary">返回面试室</RouterLink></section>
  <template v-if="report?.status === 'ready'">
    <section class="card report-summary"><span class="report-check"><CheckCheck :size="28" /></span><div><h2>完成一场练习，就是向前一步。</h2><p>{{ report.summary }}</p></div></section>
    <div class="coverage-grid"><section class="card" v-for="item in [{ label: '计划主问题', count: report.coverage.planned }, { label: '实际回答', count: report.coverage.answered }, { label: '已跳过', count: report.coverage.skipped }, { label: '尚未到达', count: report.coverage.not_reached }]" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.count }}<small>题</small></strong></section></div>
    <div class="mock-notice"><FlaskConical :size="18" /><span>当前不提供总分或维度分。固定追问不代表回答质量，Mock 记录不能作为真实模型效果或真实用户测试。</span></div>
    <section class="card report-transcript"><div class="section-heading"><h2>本次问答记录</h2><span class="muted">完整正式消息，按实际顺序保存</span></div><div v-for="message in report.messages" :key="message.id" class="transcript-item" :class="message.speaker"><span>{{ message.speaker === 'user' ? '你' : message.speaker === 'system' ? '状态' : 'TalentGo · Mock' }}</span><p>{{ message.content }}</p></div></section>
    <div class="report-actions"><RouterLink to="/history" class="button secondary">回顾训练记录</RouterLink><RouterLink to="/practice" class="button primary">再准备一次 <ArrowRight :size="16" /></RouterLink></div>
  </template>
</template>
