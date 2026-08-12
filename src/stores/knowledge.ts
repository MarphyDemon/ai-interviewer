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

  async function upload(files: File[]) {
    await knowledgeApi.uploadKnowledge(files)
    await fetchDocs()
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
