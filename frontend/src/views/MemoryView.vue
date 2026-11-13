<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ApiError, request, randomKey } from '../api/client'
import { useIdentityStore } from '../stores/identity'
defineEmits<{ 'create-identity': [] }>()
interface Memory {id:string;kind:string;topic:string;content:string;role:string|null;mode:string|null;version:number;confirmed:boolean;source_type:string;source_session_id:string|null}
const identity=useIdentityStore()
const items=ref<Memory[]>([]), error=ref(''), busy=ref(false), more=ref<number|null>(null), revision=ref(0)
const editing=ref<Memory|null>(null)
const form=reactive({kind:'preference',topic:'反馈方式',content:'',role:null as string|null,mode:null as string|null})
let epoch=0
let pending:{signature:string;key:string}|null=null
async function load(offset=0){
 const token=identity.identity?.token, ticket=epoch
 if(!token)return
 try{const r=await request<{items:Memory[];next_offset:number|null;memory_revision:number}>(`/memories?offset=${offset}`,{},token)
 if(ticket===epoch){items.value=offset?[...items.value,...r.items]:r.items;more.value=r.next_offset;revision.value=r.memory_revision}}
 catch(e){if(ticket===epoch)error.value=e instanceof Error?e.message:'记忆读取失败'}
}
watch(()=>identity.activeId,()=>{epoch++;items.value=[];editing.value=null;error.value='';pending=null;busy.value=false;form.content='';void load()},{immediate:true})
async function mutate(path:string,method:string,body?:unknown){
 const token=identity.identity?.token,ticket=epoch
 if(!token||busy.value)return false
 busy.value=true;error.value=''
 const text=body?JSON.stringify(body):undefined,signature=method+path+(text||'')
 if(pending?.signature!==signature)pending={signature,key:randomKey()}
 try{await request(path,{method,headers:{'Idempotency-Key':pending.key},body:text},token)
 if(ticket!==epoch)return false
 pending=null;await load();return true
 }catch(e){if(ticket===epoch){error.value=e instanceof Error?e.message:'保存失败';if(!(e instanceof ApiError)||e.status!==0)pending=null}return false}
 finally{if(ticket===epoch)busy.value=false}
}
async function save(){
 const row=editing.value
 if(await mutate(row?`/memories/${row.id}`:'/memories',row?'PATCH':'POST',row?{expected_version:row.version,topic:form.topic,content:form.content}:{...form})){
 editing.value=null;form.content=''
 }
}
function edit(row:Memory){editing.value=row;Object.assign(form,{kind:row.kind,topic:row.topic,content:row.content,role:row.role,mode:row.mode})}
function remove(row:Memory){if(window.confirm('永久删除这条记忆？后续生成不再注入，已保存问答和报告保留。'))void mutate(`/memories/${row.id}?expected_version=${row.version}`,'DELETE')}
</script>
<template>
<section class="page-heading"><div><div class="eyebrow">YOU DECIDE WHAT STAYS</div><h1>让下一次练习，更懂你。</h1><p>明确保存目标与偏好，随时纠正。系统推断须确认后才会用于训练。</p></div><span class="subtle-tag">记忆版本 {{revision}}</span></section>
<section v-if="!identity.identity" class="card empty-profile"><h2>先选择训练身份</h2><button class="button primary" @click="$emit('create-identity')">选择身份</button></section>
<template v-else>
<p v-if="error" class="error-banner" role="alert">{{error}} <button @click="load()">刷新</button></p>
<div class="memory-layout"><form class="card memory-form" @submit.prevent="save"><h2>{{editing?'纠正这条记忆':'明确保存一条记忆'}}</h2><fieldset :disabled="busy"><label for="memory-kind">类型</label><select id="memory-kind" v-model="form.kind" :disabled="!!editing"><option value="preference">反馈偏好</option><option value="goal">训练目标</option><option value="weakness">自述薄弱点</option></select><label for="memory-topic">主题</label><input id="memory-topic" v-model="form.topic" required maxlength="80"/><label for="memory-content">内容</label><textarea id="memory-content" v-model="form.content" rows="4" maxlength="1200" required placeholder="例如：反馈先给结论，再解释一个例子。"/><template v-if="!editing"><label for="memory-role">适用岗位</label><select id="memory-role" v-model="form.role"><option :value="null">所有岗位</option><option value="frontend">前端</option><option value="backend">后端</option></select><label for="memory-mode">适用模式</label><select id="memory-mode" v-model="form.mode"><option :value="null">所有模式</option><option value="technical">技术</option><option value="behavioral">行为</option><option value="pressure">压力</option></select></template></fieldset><p class="field-help">弱项按精确主题匹配，例如「浏览器基础」；目标和偏好可跨主题使用。纠正内容会成为你明确确认的信息。</p><div class="form-actions"><button v-if="editing" type="button" class="button secondary" @click="editing=null;form.content=''">取消编辑</button><button class="button primary" :disabled="busy">{{busy?'保存中…':'保存记忆'}}</button></div></form>
<div class="memory-list"><section v-if="!items.length" class="card memory-item"><h3>还没有保存记忆</h3><p>可先保存一条反馈偏好。启用系统推断后，有效报告也可产生待确认弱项。</p></section><section v-for="row in items" :key="row.id" class="card memory-item"><div class="section-heading"><h3>{{row.topic}}</h3><span class="subtle-tag">v{{row.version}} · {{row.confirmed?'已确认':'待确认'}}</span></div><p class="memory-content">{{row.content}}</p><p class="field-help">{{row.source_type==='user_explicit'?'你明确保存':'系统推断，不是事实结论'}} · {{row.role||'全部岗位'}} · {{row.mode||'全部模式'}}</p><RouterLink v-if="row.source_session_id" :to="`/sessions/${row.source_session_id}/report`" class="text-link">查看来源报告</RouterLink><div class="form-actions"><button v-if="!row.confirmed" class="button primary" :disabled="busy" @click="mutate(`/memories/${row.id}`,'PATCH',{expected_version:row.version,confirmed:true})">确认用于后续训练</button><button class="button secondary" :disabled="busy" @click="edit(row)">纠正</button><button class="text-link" :disabled="busy" @click="remove(row)">删除</button></div></section><button v-if="more!==null" class="button secondary" @click="load(more!)">加载更多</button></div></div>
<p class="mock-notice">系统推断开关在训练档案中，默认关闭；关闭后历史推断也不注入。修改/删除会失效摘要并丢弃运行中的旧结果，需重试原操作。历史问答与报告不自动删除。</p>
</template>
</template>
<style scoped>.memory-layout{display:grid;grid-template-columns:minmax(260px,.8fr) 1.2fr;gap:24px;align-items:start}.memory-form,.memory-item{padding:24px}.memory-form label{margin:18px 0 8px}.memory-list{display:grid;gap:16px}.memory-content{line-height:1.9;white-space:pre-wrap;margin-top:16px}.memory-item .form-actions{justify-content:flex-start;flex-wrap:wrap}.field-help{margin-top:12px}@media(max-width:1000px){.memory-layout{grid-template-columns:1fr}}</style>
