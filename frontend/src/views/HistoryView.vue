<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowRight, Clock3, FlaskConical, Plus } from '@lucide/vue'
import { getSessions } from '../api/sessions'
import { useIdentityStore } from '../stores/identity'
import { MODE_LABELS, STATUS_LABELS, type InterviewSession } from '../types/session'
defineEmits<{ 'create-identity': [] }>()
const identity = useIdentityStore()
const items = ref<InterviewSession[]>([])
const cursor = ref<string | null>(null)
const busy = ref(false)
const error = ref('')
let epoch = 0
async function load(more = false) {
  const current = identity.identity
  if (!current) return
  const ticket = ++epoch
  busy.value = true
  error.value = ''
  try {
    const page = await getSessions(current.token, more ? cursor.value || undefined : undefined)
    if (ticket !== epoch) return
    items.value = more ? [...items.value, ...page.items] : page.items
    cursor.value = page.next_cursor
  } catch (e) { if (ticket === epoch) error.value = e instanceof Error ? e.message : '读取失败' }
  finally { if (ticket === epoch) busy.value = false }
}
watch(() => identity.activeId, () => { epoch++; items.value = []; cursor.value = null; void load() }, { immediate: true })
</script>

<template>
  <section class="page-heading"><div><div class="eyebrow"><span></span> YOUR PRACTICE, KEPT</div><h1>每一次练习，都有迹可循。</h1><p>继续未完成的对话，或回顾已经保存的 Mock 问答。</p></div><RouterLink to="/practice" class="button primary"><Plus :size="16" />新的练习</RouterLink></section>
  <section v-if="!identity.identity" class="card empty-profile"><Clock3 :size="30" /><h2>选择身份，查看自己的记录</h2><p>其他身份的训练不会出现在这里。</p><button class="button primary" @click="$emit('create-identity')">选择训练身份</button></section>
  <p v-if="error" class="error-banner" role="alert">{{ error }}<button @click="load()">重试</button></p>
  <section v-if="identity.identity && !busy && !items.length" class="card empty-profile"><h2>你的第一场练习，正在等你。</h2><p>当前没有面试记录，也不会为你预置虚构成绩。</p><RouterLink to="/practice" class="button primary">创建练习 <ArrowRight :size="16" /></RouterLink></section>
  <div class="history-list"><RouterLink v-for="session in items" :key="session.id" :to="`/sessions/${session.id}${session.status === 'completed' ? '/report' : ''}`" class="card history-item"><span class="icon-box"><FlaskConical :size="20" /></span><div><h2>{{ session.title }}</h2><p>{{ session.role === 'frontend' ? '前端开发' : session.role === 'backend' ? '后端开发' : '岗位待确认' }} · {{ session.mode ? MODE_LABELS[session.mode] : '类型待确认' }} · {{ new Date(session.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}</p></div><div class="history-meta"><span class="subtle-tag">{{ STATUS_LABELS[session.status] }}</span><small>{{ session.coverage.answered }} 题已回答 · Mock</small></div><ArrowRight :size="17" /></RouterLink></div>
  <button v-if="cursor" class="button secondary" :disabled="busy" @click="load(true)">{{ busy ? '读取中…' : '查看更多记录' }}</button>
</template>
