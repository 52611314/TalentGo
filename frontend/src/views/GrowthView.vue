<script setup lang="ts">
import { ref,watch } from 'vue'
import { request } from '../api/client'
import { useIdentityStore } from '../stores/identity'
import { MODE_LABELS } from '../types/session'
defineEmits<{ 'create-identity': [] }>()
interface Task {id:string;topic:string;instruction:string;role:string;mode:string;status:string;source_session_id:string;rubric_version:string}
interface Group {role:string;mode:string;rubric_version:string;points:{session_id:string;score:number;created_at:string;coverage:{scored:number;planned:number};model_name:string;prompt_version:string}[]}
const identity=useIdentityStore(), tasks=ref<Task[]>([]),groups=ref<Group[]>([]),error=ref(''),notice=ref(''),loading=ref(false)
const taskOffset=ref<number|null>(null),trendOffset=ref<number|null>(null)
let epoch=0
async function loadTasks(offset=0){const token=identity.identity?.token,ticket=epoch;if(!token)return
const r=await request<{items:Task[];next_offset:number|null}>(`/practice-tasks?offset=${offset}`,{},token)
if(ticket===epoch){tasks.value=offset?[...tasks.value,...r.items]:r.items;taskOffset.value=r.next_offset}}
async function loadTrends(offset=0){const token=identity.identity?.token,ticket=epoch;if(!token)return
const r=await request<{groups:Group[];next_offset:number|null;notice:string}>(`/reports/trends?offset=${offset}`,{},token)
if(ticket===epoch){for(const g of r.groups){const current=offset?groups.value.find(x=>x.role===g.role&&x.mode===g.mode&&x.rubric_version===g.rubric_version):null;if(current)current.points.push(...g.points);else groups.value.push(g)}trendOffset.value=r.next_offset;notice.value=r.notice}}
async function load(){const ticket=epoch;loading.value=true;error.value='';try{await Promise.all([loadTasks(),loadTrends()])}catch(e){if(ticket===epoch)error.value=e instanceof Error?e.message:'读取失败'}finally{if(ticket===epoch)loading.value=false}}
async function more(kind:'task'|'trend'){try{if(kind==='task'&&taskOffset.value!==null)await loadTasks(taskOffset.value);if(kind==='trend'&&trendOffset.value!==null)await loadTrends(trendOffset.value)}catch(e){error.value=e instanceof Error?e.message:'读取失败'}}
watch(()=>identity.activeId,()=>{epoch++;tasks.value=[];groups.value=[];taskOffset.value=null;trendOffset.value=null;void load()},{immediate:true})
</script>
<template>
<section class="page-heading"><div><div class="eyebrow">ONE GAP, ONE NEXT STEP</div><h1>从一个缺口，开始下一次练习。</h1><p>任务来自有效最终评价，完成对应主题的有效作答后更新状态。</p></div></section>
<section v-if="!identity.identity" class="card empty-profile"><button class="button primary" @click="$emit('create-identity')">选择训练身份</button></section>
<template v-else><p v-if="error" class="error-banner" role="alert">{{error}} <button @click="groups=[];load()">刷新</button></p>
<section class="card growth-empty" v-if="!tasks.length && !loading"><h2>还没有需要复练的任务</h2><p>完成真实模型训练后，有依据的缺口会生成任务。Mock 不生成任务。</p><RouterLink to="/practice" class="button primary">开始练习</RouterLink></section>
<div class="task-grid"><section class="card task-card" v-for="task in tasks" :key="task.id"><div class="section-heading"><h2>{{task.topic}}</h2><span class="subtle-tag">{{ task.status==='pending'?'待复练':task.status==='in_progress'?'进行中':'已完成' }}</span></div><p>{{task.instruction}}</p><p class="field-help">{{task.role==='frontend'?'前端':'后端'}} · {{MODE_LABELS[task.mode as keyof typeof MODE_LABELS]}} · {{task.rubric_version}}</p><div class="form-actions"><RouterLink :to="`/sessions/${task.source_session_id}/report`" class="text-link">查看来源</RouterLink><RouterLink v-if="task.status==='pending'" :to="`/practice?task=${task.id}`" class="button primary">针对这个主题复练</RouterLink><RouterLink v-if="task.status==='in_progress'" to="/history" class="button secondary">从训练记录继续</RouterLink></div></section></div>
<button v-if="taskOffset!==null" class="button secondary" @click="more('task')">更多任务</button>
<div class="section-heading trend-heading"><h2>同一评分版本下，回看每一次训练</h2></div><p class="mock-notice">{{loading?'正在读取评分记录…':error?'评分记录暂未完整读取，请重试。':notice||'尚无有效真实评分；不会展示虚构趋势。'}}</p>
<section v-for="group in groups" :key="group.role+group.mode+group.rubric_version" class="card trend-card"><h3>{{group.role==='frontend'?'前端':'后端'}} · {{MODE_LABELS[group.mode as keyof typeof MODE_LABELS]}} · {{group.rubric_version}}</h3><div v-for="p in group.points" :key="p.session_id" class="trend-point"><RouterLink :to="`/sessions/${p.session_id}/report`">{{new Date(p.created_at).toLocaleDateString('zh-CN')}} · {{p.model_name}} · {{p.prompt_version}}</RouterLink><div class="progress-track"><span :style="{width:`${p.score}%`}"></span></div><strong>{{p.score}} / 100</strong><small>有效 {{p.coverage.scored}} / 计划 {{p.coverage.planned}} 题</small></div></section><button v-if="trendOffset!==null" class="button secondary" @click="more('trend')">更多评分记录</button>
</template>
</template>
<style scoped>.task-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.task-card,.trend-card,.growth-empty{padding:25px}.task-card h2{font-size:18px}.task-card p{line-height:1.9;margin:16px 0}.task-card .form-actions{flex-wrap:wrap}.growth-empty p{margin:16px 0;line-height:1.8}.trend-heading{margin-top:40px}.trend-card{margin:20px 0}.trend-point{display:grid;grid-template-columns:1fr 130px;gap:12px;padding:20px 0;border-bottom:1px solid #ece9f1}.trend-point a{font-size:12px;line-height:1.7}.trend-point .progress-track{grid-row:2;grid-column:1}.trend-point small{font-size:11px;color:#767080}@media(max-width:900px){.task-grid{grid-template-columns:1fr}}</style>
