import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { KnowledgeDoc } from '@/types'
import * as knowledgeApi from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const docs = ref<KnowledgeDoc[]>([])
  const loading = ref(false)

  async function fetchDocs() {
    loading.value = true
    try {
      docs.value = await knowledgeApi.getKnowledgeList()
    } finally {
      loading.value = false
    }
  }

  async function pollStatus(id: number, interval = 1000, maxRetries = 60) {
    for (let i = 0; i < maxRetries; i++) {
      await new Promise((r) => setTimeout(r, interval))
      const status = await knowledgeApi.getKnowledgeStatus(id)
      const doc = docs.value.find((d) => d.id === id)
      if (doc) doc.status = status.status as KnowledgeDoc['status']
      if (status.status === 'ready' || status.status === 'failed') {
        // 状态完成后重新拉取列表，获取 LLM 提取的 position/difficulty/title/tags
        await fetchDocs()
        break
      }
    }
  }

  async function upload(files: File[]) {
    const res = await knowledgeApi.uploadKnowledge(files)
    await fetchDocs()
    // 轮询所有新上传的文档状态
    for (const id of res.ids) {
      pollStatus(id)
    }
  }

  async function remove(id: number) {
    await knowledgeApi.deleteKnowledge(id)
    await fetchDocs()
  }

  async function checkStatus(id: number) {
    const res = await knowledgeApi.getKnowledgeStatus(id)
    const doc = docs.value.find((d) => d.id === id)
    if (doc) doc.status = res.status as KnowledgeDoc['status']
    return res.status
  }

  return { docs, loading, fetchDocs, upload, remove, checkStatus }
})
