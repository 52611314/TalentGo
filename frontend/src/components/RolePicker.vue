<script setup lang="ts">
import { computed, getCurrentInstance, onMounted, ref } from 'vue'
import { loadRoles, roleLabel, roles } from '../data/roles'

const props = withDefaults(defineProps<{ modelValue: string | null; secondaryRoles?: string[]; multiple?: boolean; disabled?: boolean }>(), { secondaryRoles: () => [], multiple: false, disabled: false })
const emit = defineEmits<{ 'update:modelValue': [value: string | null]; 'update:secondaryRoles': [value: string[]] }>()
const query = ref('')
const error = ref('')
const searchId = `role-search-${getCurrentInstance()?.uid}`
const selected = computed(() => [props.modelValue, ...props.secondaryRoles].filter((x): x is string => !!x))
const filtered = computed(() => {
  const keywords = query.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean)
  return roles.value.filter(item => keywords.every(word => [item.label, item.id, item.group, item.focus, ...item.aliases].join(' ').toLocaleLowerCase().includes(word)))
})
async function load() { error.value = ''; try { await loadRoles() } catch { error.value = '岗位列表暂时无法加载，请重试' } }
onMounted(load)
function choose(id: string) {
  if (props.disabled) return
  if (!props.multiple) { emit('update:modelValue', id === props.modelValue ? null : id); return }
  if (id === props.modelValue) {
    emit('update:modelValue', props.secondaryRoles[0] || null)
    emit('update:secondaryRoles', props.secondaryRoles.slice(1))
  } else if (props.secondaryRoles.includes(id)) emit('update:secondaryRoles', props.secondaryRoles.filter(role => role !== id))
  else if (!props.modelValue) emit('update:modelValue', id)
  else if (selected.value.length < 3) emit('update:secondaryRoles', [...props.secondaryRoles, id])
}
function primary(id: string) {
  emit('update:secondaryRoles', [props.modelValue!, ...props.secondaryRoles.filter(role => role !== id)])
  emit('update:modelValue', id)
}
function move(event: KeyboardEvent, offset: number) {
  const buttons = Array.from((event.currentTarget as HTMLElement).querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
  const index = buttons.indexOf(event.target as HTMLButtonElement)
  buttons[(index + offset + buttons.length) % buttons.length]?.focus()
  event.preventDefault()
}
</script>

<template>
  <div class="role-picker">
    <div v-if="selected.length" class="role-selected" aria-live="polite">
      <div v-for="(id, index) in selected" :key="id" class="role-chip" :class="{ primary: index === 0 }">
        <span class="role-rank">{{ index === 0 ? '主岗位' : '次选' }}</span><strong>{{ roleLabel(id) }}</strong>
        <button v-if="index && multiple" type="button" :disabled="disabled" @click="primary(id)">设为主岗位</button>
        <button type="button" :disabled="disabled" :aria-label="`移除${roleLabel(id)}`" @click="choose(id)">×</button>
      </div>
    </div>
    <label :for="searchId">搜索岗位</label>
    <input :id="searchId" v-model="query" type="search" :disabled="disabled" placeholder="输入岗位或关键词，如 AI、测试、Java" autocomplete="off" />
    <p class="field-help">{{ filtered.length }} / {{ roles.length }} 个岗位{{ multiple ? ' · 最多选择 3 个，首选为主岗位' : ' · 选择一个目标岗位' }}。支持上下方向键浏览。</p>
    <div class="role-list" aria-label="岗位列表" @keydown.down="move($event, 1)" @keydown.up="move($event, -1)">
      <button v-for="item in filtered" :key="item.id" type="button" :disabled="disabled || (multiple && selected.length >= 3 && !selected.includes(item.id))" :aria-pressed="selected.includes(item.id)" :class="{ chosen: selected.includes(item.id) }" @click="choose(item.id)">
        <span><strong>{{ item.label }}</strong><small>{{ item.group }} · {{ item.focus }}</small></span><b>{{ item.id === modelValue ? '主岗位' : secondaryRoles.includes(item.id) ? '次选' : '＋' }}</b>
      </button>
      <p v-if="roles.length && !filtered.length" class="field-help">未找到匹配岗位，试试其他关键词。</p>
    </div>
    <p v-if="error" class="error-text" role="alert">{{ error }} <button type="button" @click="load">重新加载</button></p>
  </div>
</template>
