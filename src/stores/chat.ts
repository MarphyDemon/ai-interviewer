import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatConversation, ChatMessageItem } from '@/types'
import * as chatApi from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<ChatConversation[]>([])
  const currentMessages = ref<ChatMessageItem[]>([])
  const currentId = ref<number | null>(null)
  const streaming = ref(false)
  const conversationsLoading = ref(false)
  const selectLoading = ref(false)
  const removeLoading = ref<number | null>(null)
  const newConversationLoading = ref(false)
  let abortController: AbortController | null = null

  async function fetchConversations() {
    conversationsLoading.value = true
    try {
      conversations.value = await chatApi.listConversations()
    } finally {
      conversationsLoading.value = false
    }
  }

  async function selectConversation(id: number) {
    selectLoading.value = true
    currentId.value = id
    try {
      // 正在流式接收时不覆盖消息列表，避免丢失本地已添加的消息
      if (!streaming.value) {
        currentMessages.value = await chatApi.getMessages(id)
      }
    } finally {
      selectLoading.value = false
    }
  }

  async function newConversation(options?: { skipLoadMessages?: boolean }): Promise<number> {
    newConversationLoading.value = true
    try {
      const conv = await chatApi.createConversation()
      conversations.value.unshift(conv)
      currentId.value = conv.id
      // 如果需要跳过加载消息（例如在 sendMessage 中创建新会话时）
      // 因为后续会立即添加消息，不需要从服务器加载空列表
      if (!options?.skipLoadMessages) {
        await selectConversation(conv.id)
      }
      return conv.id
    } finally {
      newConversationLoading.value = false
    }
  }

  async function rename(id: number, title: string) {
    await chatApi.renameConversation(id, title)
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) conv.title = title
  }

  async function remove(id: number) {
    removeLoading.value = id
    try {
      await chatApi.deleteConversation(id)
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentId.value === id) {
        currentId.value = null
        currentMessages.value = []
      }
    } finally {
      removeLoading.value = null
    }
  }

  async function sendMessage(message: string, onDelta?: (delta: string) => void) {
    if (!currentId.value) {
      // 创建新会话时跳过加载消息，避免覆盖后续本地添加的消息
      await newConversation({ skipLoadMessages: true })
    }
    const convId = currentId.value!

    // 立即显示用户消息
    currentMessages.value.push({
      id: Date.now(),
      role: 'user',
      content: message,
      createdAt: new Date().toISOString(),
    })

    // 助手占位消息（流式追加）
    const assistantMsg: ChatMessageItem = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
    }
    currentMessages.value.push(assistantMsg)
    // 必须取响应式代理：直接 mutate 原始对象不会触发 Vue 更新（否则只在流结束时一次性显示）
    const reactiveMsg = currentMessages.value[currentMessages.value.length - 1]

    streaming.value = true
    abortController = new AbortController()
    try {
      await chatApi.streamMessage(
        convId,
        message,
        (delta) => {
          reactiveMsg.content += delta
          onDelta?.(delta)
        },
        abortController.signal,
      )
      // 刷新会话列表（标题可能已由首条消息自动生成）
      await fetchConversations()
    } catch (e: any) {
      // 用户主动打断：保留已生成内容，不当作错误
      if (e?.name === 'AbortError') {
        if (!reactiveMsg.content) {
          currentMessages.value.pop()
        }
      } else {
        reactiveMsg.content = '⚠️ ' + (e.message || '生成失败')
      }
    } finally {
      streaming.value = false
      abortController = null
    }
  }

  /** 中断当前流式生成（保留已生成的部分内容） */
  function stopGeneration() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  return {
    conversations,
    currentMessages,
    currentId,
    streaming,
    conversationsLoading,
    selectLoading,
    removeLoading,
    newConversationLoading,
    fetchConversations,
    selectConversation,
    newConversation,
    rename,
    remove,
    sendMessage,
    stopGeneration,
  }
})
