<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Check, Fingerprint, Plus, RefreshCw, Save, ShieldCheck, UserRound, X } from '@lucide/vue'
import { useIdentityStore } from '../stores/identity'
import type { ProfileInput } from '../types/session'
import { ApiError } from '../api/client'

defineEmits<{ 'create-identity': [] }>()
const store = useIdentityStore()
const form = reactive<ProfileInput>({ target_role: null, experience_level: null, tech_stack: [], background: '', goals: '', feedback_style: 'guided', allow_inferred_memory: false })
const tag = ref('')
const saving = ref(false)
const saved = ref(false)
const error = ref('')
const sourceVersion = ref(0)
watch(() => store.profile, value => {
  if (!value) return
  const { target_role, experience_level, tech_stack, background, goals, feedback_style, allow_inferred_memory } = value
  Object.assign(form, { target_role, experience_level, tech_stack: [...tech_stack], background, goals, feedback_style, allow_inferred_memory })
  sourceVersion.value = value.version
  error.value = ''
}, { immediate: true })
const disabled = computed(() => saving.value || store.loading || !store.profile)
const updatedTime = computed(() => store.profile ? new Date(store.profile.updated_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '')
function addTag() {
  const value = tag.value.trim()
  if (value && value.length <= 50 && form.tech_stack.length < 20 && !form.tech_stack.includes(value)) form.tech_stack.push(value)
  tag.value = ''
}
async function save() {
  if (disabled.value) return
  addTag()
  saving.value = true
  saved.value = false
  error.value = ''
  try { await store.save({ ...form, tech_stack: [...form.tech_stack] }); saved.value = true; ElMessage.success('训练档案已保存') }
  catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    if (e instanceof ApiError && e.code === 'VERSION_CONFLICT') error.value += '。请先重新加载资料，再确认修改。'
  } finally { saving.value = false }
}
</script>

<template>
  <section class="page-heading"><div><div class="eyebrow"><span></span> BUILT AROUND YOU</div><h1>先了解你，再一起向前。</h1><p>告诉我们你的方向与偏好，为之后的个性化训练做好准备。</p></div><span class="milestone-pill"><ShieldCheck :size="14" /> 身份独立保存</span></section>
  <section v-if="!store.identity" class="card empty-profile"><span class="empty-symbol"><UserRound :size="32" /></span><h2>你的成长档案，从这里开始。</h2><p>创建一个匿名训练身份，保存目标、技术栈与反馈偏好。<br />无需邮箱或密码，后续可在此浏览器切换不同身份。</p><button class="button primary" @click="$emit('create-identity')">创建训练身份 <ArrowRight :size="17" /></button></section>
  <div v-else class="profile-layout">
    <form class="card profile-form" @submit.prevent="save">
      <div class="form-card-title"><span class="icon-box"><UserRound :size="19" /></span><div><h2>我的训练档案</h2><p>只填写你愿意提供的信息，之后随时可以修改。</p></div><span class="subtle-tag">v{{ sourceVersion }}</span></div>
      <p v-if="store.error" class="error-banner" role="alert">{{ store.error }} <button type="button" @click="store.refresh">重试加载</button></p>
      <fieldset :disabled="disabled"><div class="form-section"><div class="form-section-label"><span>01</span><h3>目标与起点</h3></div><label>目标岗位</label><div class="choice-grid"><button type="button" :class="{ chosen: form.target_role === 'frontend' }" @click="form.target_role = 'frontend'"><strong>前端开发</strong><small>界面交互 · 浏览器 · 工程化</small><Check v-if="form.target_role === 'frontend'" :size="16" /></button><button type="button" :class="{ chosen: form.target_role === 'backend' }" @click="form.target_role = 'backend'"><strong>后端开发</strong><small>服务设计 · 数据库 · 系统基础</small><Check v-if="form.target_role === 'backend'" :size="16" /></button></div><label for="experience">当前阶段</label><select id="experience" v-model="form.experience_level"><option :value="null">选择与你最接近的阶段</option><option value="beginner">基础学习中 · 正在建立知识体系</option><option value="intern">实习准备中 · 已有课程或项目经历</option><option value="graduate">校招准备中 · 希望深入复盘与训练</option></select><label for="tech-tag">熟悉的技术 <span class="optional">可选，最多 20 项</span></label><div class="tag-editor"><span v-for="(item, index) in form.tech_stack" :key="item" class="tech-tag">{{ item }}<button type="button" :aria-label="`移除 ${item}`" @click="form.tech_stack.splice(index, 1)"><X :size="12" /></button></span><input id="tech-tag" v-model="tag" maxlength="50" placeholder="例如 Vue、Python、PostgreSQL" @keydown.enter.prevent="addTag" /><button type="button" class="tag-add" @click="addTag" aria-label="添加技术标签"><Plus :size="16" /></button></div></div>
      <div class="form-section"><div class="form-section-label"><span>02</span><h3>你的经历与期待</h3></div><label for="background">项目或学习背景 <span class="optional">可选</span></label><textarea id="background" v-model="form.background" maxlength="4000" rows="4" placeholder="简单说说你做过的项目、正在学习的内容，不需要一份完整的简历。"></textarea><label for="goals">想重点练习什么？ <span class="optional">可选</span></label><textarea id="goals" v-model="form.goals" maxlength="4000" rows="3" placeholder="例如：把项目经历讲清楚，或补齐数据库与网络基础。"></textarea></div>
      <div class="form-section last"><div class="form-section-label"><span>03</span><h3>适合你的反馈方式</h3></div><div class="style-choices"><label v-for="option in [{ value: 'guided', title: '引导式', text: '通过问题，逐步发现改进点' }, { value: 'concise', title: '简洁直接', text: '先给重点，再给下一步' }, { value: 'detailed', title: '详细分析', text: '展开理由，解释知识与方法' }]" :key="option.value" :class="{ chosen: form.feedback_style === option.value }"><input type="radio" name="feedback_style" :value="option.value" v-model="form.feedback_style" /><span><strong>{{ option.title }}</strong><small>{{ option.text }}</small></span></label></div><label class="memory-toggle"><input type="checkbox" v-model="form.allow_inferred_memory" /><span><strong>允许系统在未来归纳训练薄弱点</strong><small>默认关闭。M1 只保存此偏好，长期记忆将在后续阶段接入。</small></span></label></div></fieldset>
      <p v-if="error" class="error-banner" role="alert">{{ error }}<button v-if="error.includes('刷新') || error.includes('重新加载')" type="button" @click="store.refresh">重新加载资料</button></p><div class="form-actions"><span class="save-state" role="status">{{ saving ? '正在保存…' : saved ? '已保存到 PostgreSQL' : store.loading ? '正在加载…' : '修改后记得保存' }}</span><button class="button primary" :disabled="disabled"><Save :size="16" />{{ saving ? '保存中…' : '保存训练档案' }}</button></div>
    </form>
    <aside class="profile-aside"><section class="card identity-card"><div class="large-avatar">{{ store.identity.display_name.slice(0, 1) }}</div><h3>{{ store.identity.display_name }}</h3><span class="identity-caption">YOUR PERSONAL SPACE</span><div class="identity-separator"></div><div class="identity-meta"><Fingerprint :size="16" /><span>匿名训练身份</span><Check :size="14" /></div><p>档案由数据库独立保存。<br />切换身份不会混用他人的资料。</p><button class="text-link" @click="$emit('create-identity')">切换或创建身份 <ArrowRight :size="15" /></button></section><section class="privacy-note"><ShieldCheck :size="21" /><h3>你决定分享什么。</h3><p>无需提供真实姓名、联系方式或敏感经历。身份凭证只保存在当前浏览器，清除本机数据后无法找回。</p><p v-if="updatedTime" class="last-updated">最近保存<br />{{ updatedTime }}</p></section></aside>
  </div>
</template>
