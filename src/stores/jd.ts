import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { JobDescription } from '@/types'
import * as jdApi from '@/api/jd'

export const useJdStore = defineStore('jd', () => {
  const jds = ref<JobDescription[]>([])
  const loading = ref(false)
  const errorMsg = ref('')

  async function fetchJds() {
    loading.value = true
    errorMsg.value = ''
    try {
      jds.value = await jdApi.listJds()
    } catch (e: any) {
      errorMsg.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createJd(title: string, content: string, position = '') {
    const jd = await jdApi.createJd(title, content, position)
    jds.value.unshift(jd)
    return jd
  }

  async function uploadJd(file: File, title = '', position = '') {
    const jd = await jdApi.uploadJd(file, title, position)
    jds.value.unshift(jd)
    return jd
  }

  async function deleteJd(id: number) {
    await jdApi.deleteJd(id)
    jds.value = jds.value.filter((j) => j.id !== id)
  }

  return {
    jds,
    loading,
    errorMsg,
    fetchJds,
    createJd,
    uploadJd,
    deleteJd,
  }
})
