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

  return { resumes, loading, fetchResumes, upload, remove }
})
