import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ResumeInfo } from '@/types'
import * as resumeApi from '@/api/resume'

export const useResumeStore = defineStore('resume', () => {
  const resumes = ref<ResumeInfo[]>([])
  const loading = ref(false)

  async function fetchResumes() {
    loading.value = true
    try {
      resumes.value = await resumeApi.getResumeList()
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File, position: string) {
    const res = await resumeApi.uploadResume(file, position)
    await fetchResumes()
    return res
  }

  async function remove(id: number) {
    await resumeApi.deleteResume(id)
    await fetchResumes()
  }

  async function rename(id: number, filename: string) {
    const updated = await resumeApi.renameResume(id, filename)
    const idx = resumes.value.findIndex((r) => r.id === id)
    if (idx !== -1) resumes.value[idx] = updated
    return updated
  }

  return { resumes, loading, fetchResumes, upload, remove, rename }
})
