<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowDown, ArrowRight, ArrowUpRight, AudioLines, Braces, Check, CheckCheck, ChevronRight, Circle, Database, FileUser, Fingerprint, Layers3, RefreshCw, Server, ShieldCheck, Sparkles, Waypoints } from '@lucide/vue'
import { request } from '../api/client'
import type { Health } from '../types/api'
import { useIdentityStore } from '../stores/identity'

defineEmits<{ 'create-identity': [] }>()
const store = useIdentityStore()
const live = ref<Health | null>(null)
const ready = ref<Health | null>(null)
const checking = ref(false)
const healthError = ref('')
const complete = computed(() => [store.profile?.target_role, store.profile?.experience_level, store.profile?.tech_stack.length, store.profile?.goals.trim()].filter(Boolean).length)
const role = computed(() => store.profile?.target_role === 'frontend' ? '前端开发' : store.profile?.target_role === 'backend' ? '后端开发' : '尚未设置')
async function checkHealth() {
  checking.value = true
  healthError.value = ''
  const results = await Promise.allSettled([request<Health>('/health/live'), request<Health>('/health/ready')])
  live.value = results[0].status === 'fulfilled' ? results[0].value : null
  ready.value = results[1].status === 'fulfilled' ? results[1].value : null
  if (results.some(x => x.status === 'rejected')) healthError.value = '部分服务暂不可用，请检查数据库与后端进程。'
  checking.value = false
}
onMounted(checkHealth)
</script>

<template>
  <section class="page-heading"><div><div class="eyebrow"><span></span> YOUR NEXT CHAPTER</div><h1>{{ store.identity ? `${store.identity.display_name}，准备好下一步了吗？` : '每一次准备，都在靠近理想的自己。' }}</h1><p>这里是你的面试成长空间。先建立档案，让接下来的训练更懂你。</p></div><span class="milestone-pill"><Layers3 :size="14" /> 场景验收 M5</span></section>
  <div class="dashboard-grid">
    <section class="hero-card">
      <div class="hero-copy"><div class="small-tag"><Sparkles :size="13" /> A LITTLE PREPARATION. A BIG DIFFERENCE.</div><h2>把下一次面试，<br />变成你的<span>主场。</span></h2><p>了解你的目标，记住你的进步。<br />为你而来的面试训练，从一份档案开始。</p><RouterLink v-if="store.identity" to="/practice" class="button dark">开始一场练习 <ArrowRight :size="17" /></RouterLink><button v-else class="button dark" @click="$emit('create-identity')">建立我的训练档案 <ArrowRight :size="17" /></button><div class="hero-footnote"><ShieldCheck :size="13" /> 已开放真实模型与独立 Mock 训练</div></div>
      <div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="art-star star-one">✦</span><span class="art-star star-two">✧</span><div class="floating-chip chip-top"><span class="chip-icon lavender"><Braces :size="18" /></span><div><b>找到你的方向</b><small>YOUR POTENTIAL, UNLOCKED.</small></div><Check :size="15" /></div><div class="art-main"><div class="art-main-top"><span class="art-talent">t<span>g</span></span><span class="art-dot"></span></div><span class="art-label">THE NEXT VERSION OF YOU</span><div class="art-graph"><i></i><i></i><i></i><i></i><i></i><i></i><span class="graph-arrow">↗</span></div><div class="art-bottom"><span>READY TO GROW</span><span>✦</span></div></div><div class="floating-chip chip-bottom"><span class="chip-icon green"><CheckCheck :size="18" /></span><div><b>让准备有迹可循</b><small>ONE STEP CLOSER.</small></div></div></div>
    </section>
    <section class="card profile-card"><div class="card-heading"><span class="icon-box"><FileUser :size="19" /></span><span class="subtle-tag">{{ store.identity ? '已建立身份' : '等待建立' }}</span></div><h3>你的训练档案</h3><p class="muted">好的练习，从认识自己开始。</p><div class="profile-progress"><span>准备进度</span><strong>{{ complete }}<small> / 4</small></strong></div><div class="progress-track"><span :style="{ width: `${complete * 25}%` }"></span></div><div class="profile-mini"><span>目标岗位</span><strong>{{ role }}</strong></div><div class="profile-mini"><span>技术标签</span><strong>{{ store.profile?.tech_stack.length ? `${store.profile.tech_stack.length} 项已添加` : '等待添加' }}</strong></div><RouterLink to="/profile" class="text-link">{{ store.identity ? '编辑我的档案' : '了解训练档案' }} <ArrowUpRight :size="16" /></RouterLink></section>
    <section class="practice-section"><div class="section-heading"><h2>选择你的练习方向 <span>TRAIN YOUR WAY</span></h2><span class="muted">技术 · 行为 · 压力 · 证据复盘</span></div><div class="practice-grid"><RouterLink to="/practice?mode=technical" class="practice-card"><div class="practice-icon violet"><Braces :size="23" /></div><span class="coming">可练习</span><h3>技术面试</h3><p>从概念理解到项目取舍，<br />练出有深度的回答。</p><div class="practice-bottom"><span>知识理解 · 技术深挖</span><ArrowUpRight :size="18" /></div></RouterLink><RouterLink to="/practice?mode=behavioral" class="practice-card"><div class="practice-icon peach"><Waypoints :size="23" /></div><span class="coming">可练习</span><h3>行为面试</h3><p>把做过的事讲清楚，<br />让你的贡献被看见。</p><div class="practice-bottom"><span>STAR 表达 · 项目经历</span><ArrowUpRight :size="18" /></div></RouterLink><RouterLink to="/practice?mode=pressure" class="practice-card"><div class="practice-icon blue"><AudioLines :size="23" /></div><span class="coming">可练习</span><h3>压力面试</h3><p>在追问与质疑中，<br />练习有条理地回应。</p><div class="practice-bottom"><span>逻辑回应 · 观点支撑</span><ArrowUpRight :size="18" /></div></RouterLink></div></section>
    <section class="card system-card"><div class="section-heading"><h3>空间运行状态</h3><button class="icon-button" @click="checkHealth" :disabled="checking" aria-label="刷新服务状态"><RefreshCw :size="15" :class="{ spinning: checking }" /></button></div><div class="service-row"><span class="service-icon"><Server :size="17" /></span><div><strong>应用服务</strong><small>FastAPI · v0.5.0</small></div><span class="status-label" :class="{ online: !!live }"><i></i>{{ live ? '运行正常' : checking ? '检查中' : '未连接' }}</span></div><div class="service-row"><span class="service-icon"><Database :size="17" /></span><div><strong>数据存储</strong><small>PostgreSQL · 6543</small></div><span class="status-label" :class="{ online: !!ready }"><i></i>{{ ready ? '连接正常' : checking ? '检查中' : '未就绪' }}</span></div><div class="service-row"><span class="service-icon"><Fingerprint :size="17" /></span><div><strong>训练身份</strong><small>独立保存 · 仅当前身份可访问</small></div><span class="status-neutral">{{ store.identity ? '已创建' : '未创建' }}</span></div><p v-if="healthError" class="error-text" role="alert">{{ healthError }}</p><div class="system-note"><ShieldCheck :size="14" /><span>真实模型会产生供应商调用费用；Mock 不调用模型。</span></div></section>
    <section class="card roadmap-card"><div><div class="eyebrow">SMALL STEPS, REAL PROGRESS</div><h3>我们正在一步步搭建你的成长空间。</h3><p>当前已接入训练记忆、来源可查的复练与分组评分记录。<br />这里不会展示虚构的训练次数或能力分数。</p></div><div class="roadmap-steps"><div class="roadmap-step done"><span><Check :size="15" /></span><div><b>01</b><strong>基础架构</strong><small>已完成</small></div></div><i></i><div class="roadmap-step"><span>2</span><div><b>02</b><strong>面试闭环</strong><small>问答与反馈已接入</small></div></div><i></i><div class="roadmap-step"><span>3</span><div><b>03</b><strong>记忆与复练</strong><small>已接入</small></div></div></div></section>
  </div>
</template>
