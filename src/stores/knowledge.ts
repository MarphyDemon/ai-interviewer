import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { KnowledgeDoc, KnowledgeVersionInfo, KnowledgeVersionDetail, CollaboratorInfo } from '@/types'
import * as knowledgeApi from '@/api/knowledge'
import type { KnowledgeScope } from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const docs = ref<KnowledgeDoc[]>([])
  const loading = ref(false)
  const versions = ref<KnowledgeVersionInfo[]>([])
  const currentVersion = ref<KnowledgeVersionDetail | null>(null)
  const collaborators = ref<CollaboratorInfo[]>([])
  const editLockId = ref<number | null>(null)

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
        await fetchDocs()
        break
      }
    }
  }

  async function upload(files: File[], scope: KnowledgeScope = 'personal') {
    const res = await knowledgeApi.uploadKnowledge(files, scope)
    await fetchDocs()
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

  // 版本管理
  async function fetchVersions(docId: number) {
    versions.value = await knowledgeApi.getKnowledgeVersions(docId)
  }

  async function fetchVersion(docId: number, versionId: number) {
    currentVersion.value = await knowledgeApi.getKnowledgeVersion(docId, versionId)
    return currentVersion.value
  }

  async function createVersion(docId: number, changeNote: string) {
    const res = await knowledgeApi.createKnowledgeVersion(docId, changeNote)
    await fetchVersions(docId)
    return res
  }

  async function rollbackVersion(docId: number, versionId: number) {
    const res = await knowledgeApi.rollbackKnowledgeVersion(docId, versionId)
    await fetchDocs()
    return res
  }

  async function deleteVersion(docId: number, versionId: number) {
    await knowledgeApi.deleteKnowledgeVersion(docId, versionId)
    await fetchVersions(docId)
  }

  // 协作锁
  async function acquireLock(docId: number) {
    const res = await knowledgeApi.acquireEditLock(docId)
    editLockId.value = res.lockId
    return res
  }

  async function releaseLock(docId: number) {
    const res = await knowledgeApi.releaseEditLock(docId)
    editLockId.value = null
    return res
  }

  // 协作者
  async function fetchCollaborators(docId: number) {
    collaborators.value = await knowledgeApi.getCollaborators(docId)
  }

  async function addCollaborator(docId: number, userId: number, permission: string) {
    await knowledgeApi.addCollaborator(docId, userId, permission)
    await fetchCollaborators(docId)
  }

  async function removeCollaborator(docId: number, collabId: number) {
    await knowledgeApi.removeCollaborator(docId, collabId)
    await fetchCollaborators(docId)
  }

  return {
    docs, loading, versions, currentVersion, collaborators, editLockId,
    fetchDocs, pollStatus, upload, remove, checkStatus,
    fetchVersions, fetchVersion, createVersion, rollbackVersion, deleteVersion,
    acquireLock, releaseLock,
    fetchCollaborators, addCollaborator, removeCollaborator,
  }
})