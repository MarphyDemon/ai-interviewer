import client from './client'
import type { ChatConversation, ChatMessageItem } from '@/types'

export function listConversations(): Promise<ChatConversation[]> {
  return client.get('/chat/conversations')
}

export function createConversation(title?: string): Promise<ChatConversation> {
  return client.post('/chat/conversations', { title: title || null })
}

export function getMessages(convId: number): Promise<ChatMessageItem[]> {
  return client.get(`/chat/conversations/${convId}/messages`)
}

export function renameConversation(convId: number, title: string): Promise<void> {
  return client.patch(`/chat/conversations/${convId}`, { title })
}

export function deleteConversation(convId: number): Promise<void> {
  return client.delete(`/chat/conversations/${convId}`)
}

/**
 * 流式发送消息（SSE）。onDelta 收到增量文本，返回完整回复。
 */
export async function streamMessage(
  convId: number,
  message: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  const resp = await fetch(`/api/chat/conversations/${convId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(text || `请求失败 (${resp.status})`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') return full
      try {
        const parsed = JSON.parse(data)
        if (parsed.error) throw new Error(parsed.error)
        if (parsed.delta) {
          full += parsed.delta
          onDelta(parsed.delta)
        }
      } catch {
        // 非 JSON 帧忽略
      }
    }
  }
  return full
}
