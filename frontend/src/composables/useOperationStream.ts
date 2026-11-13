import { onBeforeUnmount, ref } from 'vue'
import { API_BASE } from '../api/client'
import { getOperation } from '../api/operations'

export function useOperationStream() {
  const partial = ref('')
  const streamError = ref('')
  const connected = ref(false)
  let controller: AbortController | null = null
  let epoch = 0

  function stop() {
    epoch++
    controller?.abort()
    controller = null
    connected.value = false
    partial.value = ''
  }

  async function attach(operationId: string, token: string, onTerminal: () => Promise<void>) {
    stop()
    const ticket = epoch
    const ownController = new AbortController()
    controller = ownController
    streamError.value = ''
    let lastId = ''
    for (let connectionAttempt = 0; connectionAttempt < 4 && ticket === epoch; connectionAttempt++) {
      try {
        const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
        if (lastId) headers['Last-Event-ID'] = lastId
        const response = await fetch(`${API_BASE}/operations/${operationId}/events`, { headers, signal: ownController.signal })
        if (ticket !== epoch) return
        if (response.status === 410) {
          await onTerminal()
          return
        }
        if (!response.ok || !response.body) throw new Error('事件订阅暂不可用')
        connected.value = true
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let terminal = false
        while (ticket === epoch) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
          let boundary: number
          while ((boundary = buffer.indexOf('\n\n')) >= 0) {
            const frame = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary + 2)
            const lines = frame.split('\n')
            const id = lines.find(x => x.startsWith('id: '))?.slice(4)
            const event = lines.find(x => x.startsWith('event: '))?.slice(7)
            const data = lines.filter(x => x.startsWith('data: ')).map(x => x.slice(6)).join('\n')
            if (!id || id === lastId || !data || ticket !== epoch) continue
            lastId = id
            const payload = JSON.parse(data)
            if (event === 'operation.started') partial.value = ''
            if (event === 'text.delta') partial.value += payload.text
            if (['operation.succeeded', 'operation.failed', 'operation.cancelled'].includes(event || '')) {
              terminal = true
            }
          }
        }
        if (ticket !== epoch) return
        const snapshot = await getOperation(operationId, token)
        if (['succeeded', 'failed', 'cancelled'].includes(snapshot.status)) {
          connected.value = false
          partial.value = ''
          await onTerminal()
          return
        }
        throw new Error('事件连接中断')
      } catch {
        if (ownController.signal.aborted || ticket !== epoch) return
        connected.value = false
        if (connectionAttempt === 3) {
          streamError.value = '事件连接中断。答案不会重新发送，请刷新会话状态或重新连接。'
          return
        }
        await new Promise(resolve => setTimeout(resolve, 300 * (connectionAttempt + 1)))
      }
    }
  }

  onBeforeUnmount(stop)
  return { partial, streamError, connected, attach, stop }
}
