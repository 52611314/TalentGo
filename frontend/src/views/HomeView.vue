<script setup lang="ts">
import { roleLabel } from '../data/roles'
import { computed } from 'vue'
import { ArrowRight, ArrowUpRight, AudioLines, Braces, Check, CheckCheck, FileUser, Layers3, ShieldCheck, Sparkles, Waypoints } from '@lucide/vue'
import { useIdentityStore } from '../stores/identity'

defineEmits<{ 'create-identity': [] }>()
const store = useIdentityStore()
const complete = computed(() => [store.profile?.target_role, store.profile?.experience_level, store.profile?.tech_stack.length, store.profile?.goals.trim()].filter(Boolean).length)
const role = computed(() => store.profile?.target_role ? roleLabel(store.profile.target_role) : '尚未设置')
</script>

<template>
  <section class="page-heading"><div><div class="eyebrow"><span></span> YOUR NEXT CHAPTER</div><h1>{{ store.identity ? `${store.identity.display_name}，准备好下一步了吗？` : '每一次准备，都在靠近理想的自己。' }}</h1><p>这里是你的面试成长空间。先建立档案，让接下来的训练更懂你。</p></div><span class="milestone-pill"><Layers3 :size="14" /> 你的面试成长空间</span></section>
  <div class="dashboard-grid home-grid">
    <section class="hero-card">
      <div class="hero-copy"><div class="small-tag"><Sparkles :size="13" /> A LITTLE PREPARATION. A BIG DIFFERENCE.</div><h2>把下一次面试，<br />变成你的<span>主场。</span></h2><p>了解你的目标，记住你的进步。<br />为你而来的面试训练，从一份档案开始。</p><RouterLink v-if="store.identity" to="/practice" class="button dark">开始一场练习 <ArrowRight :size="17" /></RouterLink><button v-else class="button dark" @click="$emit('create-identity')">建立我的训练档案 <ArrowRight :size="17" /></button><div class="hero-footnote"><ShieldCheck :size="13" /> 已开放真实模型与独立 Mock 训练</div></div>
      <div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="art-star star-one">✦</span><span class="art-star star-two">✧</span><div class="floating-chip chip-top"><span class="chip-icon lavender"><Braces :size="18" /></span><div><b>找到你的方向</b><small>YOUR POTENTIAL, UNLOCKED.</small></div><Check :size="15" /></div><div class="art-main"><div class="art-main-top"><span class="art-talent">t<span>g</span></span><span class="art-dot"></span></div><span class="art-label">THE NEXT VERSION OF YOU</span><div class="art-graph"><i></i><i></i><i></i><i></i><i></i><i></i><span class="graph-arrow">↗</span></div><div class="art-bottom"><span>READY TO GROW</span><span>✦</span></div></div><div class="floating-chip chip-bottom"><span class="chip-icon green"><CheckCheck :size="18" /></span><div><b>让准备有迹可循</b><small>ONE STEP CLOSER.</small></div></div></div>
    </section>
    <section class="card profile-card"><div class="card-heading"><span class="icon-box"><FileUser :size="19" /></span><span class="subtle-tag">{{ store.identity ? '已登录' : '等待建立' }}</span></div><h3>你的训练档案</h3><p class="muted">好的练习，从认识自己开始。</p><div class="profile-progress"><span>准备进度</span><strong>{{ complete }}<small> / 4</small></strong></div><div class="progress-track"><span :style="{ width: `${complete * 25}%` }"></span></div><div class="profile-mini"><span>目标岗位</span><strong>{{ role }}</strong></div><div class="profile-mini"><span>技术标签</span><strong>{{ store.profile?.tech_stack.length ? `${store.profile.tech_stack.length} 项已添加` : '等待添加' }}</strong></div><RouterLink to="/profile" class="text-link">{{ store.identity ? '编辑我的档案' : '了解训练档案' }} <ArrowUpRight :size="16" /></RouterLink></section>
    <section class="practice-section"><div class="section-heading"><h2>选择你的练习方向 <span>TRAIN YOUR WAY</span></h2><span class="muted">技术 · 行为 · 压力 · 证据复盘</span></div><div class="practice-grid"><RouterLink to="/practice?mode=technical" class="practice-card"><div class="practice-icon violet"><Braces :size="23" /></div><span class="coming">可练习</span><h3>技术面试</h3><p>从概念理解到项目取舍，<br />练出有深度的回答。</p><div class="practice-bottom"><span>知识理解 · 技术深挖</span><ArrowUpRight :size="18" /></div></RouterLink><RouterLink to="/practice?mode=behavioral" class="practice-card"><div class="practice-icon peach"><Waypoints :size="23" /></div><span class="coming">可练习</span><h3>行为面试</h3><p>把做过的事讲清楚，<br />让你的贡献被看见。</p><div class="practice-bottom"><span>STAR 表达 · 项目经历</span><ArrowUpRight :size="18" /></div></RouterLink><RouterLink to="/practice?mode=pressure" class="practice-card"><div class="practice-icon blue"><AudioLines :size="23" /></div><span class="coming">可练习</span><h3>压力面试</h3><p>在追问与质疑中，<br />练习有条理地回应。</p><div class="practice-bottom"><span>逻辑回应 · 观点支撑</span><ArrowUpRight :size="18" /></div></RouterLink></div></section>

    <section class="card roadmap-card"><div><div class="eyebrow">SMALL STEPS, REAL PROGRESS</div><h3>让每一次练习，都有下一步。</h3><p>回顾回答中的证据与建议，挑选需要加强的主题。<br />通过针对性练习，逐步积累自己的准备记录。</p></div><div class="roadmap-steps"><RouterLink to="/profile" class="text-link">明确目标 →</RouterLink><RouterLink to="/practice" class="text-link">开始面试 →</RouterLink><RouterLink to="/growth" class="text-link">专项练习 →</RouterLink></div></section>
  </div>
</template>
