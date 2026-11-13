import { ref } from 'vue'
import { getMessages, getSession } from '../api/sessions'
import type { InterviewMessage, InterviewSession } from '../types/session'

export function useSessionRecovery() {
  const session = ref<InterviewSession | null>(null)
  const messages = ref<InterviewMessage[]>([])
  const loading = ref(false)
  const error = ref('')
  let epoch = 0

  function reset() {
    epoch++
    session.value = null
    messages.value = []
    error.value = ''
    loading.value = false
  }

  async function load(id: string, token: string) {
    const ticket = ++epoch
    loading.value = true
    error.value = ''
    try {
      const snapshot = await getSession(id, token)
      const all: InterviewMessage[] = []
      let cursor: string | undefined
      do {
        const page = await getMessages(id, token, cursor)
        all.push(...page.items)
        cursor = page.next_cursor || undefined
      } while (cursor && ticket === epoch)
      if (ticket !== epoch) return false
      session.value = snapshot
      messages.value = all
      return true
    } catch (e) {
      if (ticket === epoch) error.value = e instanceof Error ? e.message : '读取面试失败'
      return false
    } finally { if (ticket === epoch) loading.value = false }
  }
  return { session, messages, loading, error, load, reset }
}
