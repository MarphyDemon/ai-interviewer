<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as adminApi from '@/api/admin'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { LLMConfig } from '@/types'

const { t } = useI18n()
const knowledgeStore = useKnowledgeStore()
const verified = ref(false)
const password = ref('')
const configs = ref<LLMConfig[]>([])
const loading = ref(false)

const showAddForm = ref(false)
const newName = ref('')
const newBaseUrl = ref('https://api.deepseek.com')
const newApiKey = ref('')
const newModel = ref('deepseek-chat')

// 知识库管理
const knowledgeFileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

onMounted(async () => {
  const token = localStorage.getItem('admin_token')
  if (!token) return
  verified.value = true
  try {
    await fetchConfigs()
    await knowledgeStore.fetchDocs()
  } catch {
    // token 过期/无效：清掉并回到口令校验
    localStorage.removeItem('admin_token')
    verified.value = false
    configs.value = []
  }
})

async function verify() {
  try {
    const res = await adminApi.verifyAdmin(password.value)
    localStorage.setItem('admin_token', res.token)
    verified.value = true
    fetchConfigs()
    knowledgeStore.fetchDocs()
  } catch {
    alert(t('admin.wrongPassword'))
  }
}

async function fetchConfigs() {
  loading.value = true
  try {
    configs.value = await adminApi.getLLMConfigs()
  } finally {
    loading.value = false
  }
}

async function addConfig() {
  try {
    await adminApi.createLLMConfig({
      name: newName.value,
      baseUrl: newBaseUrl.value,
      apiKey: newApiKey.value,
      model: newModel.value,
    })
    showAddForm.value = false
    newName.value = ''
    newApiKey.value = ''
    await fetchConfigs()
  } catch (e: any) {
    alert(t('admin.addFailed') + e.message)
  }
}

async function activate(id: number) {
  try {
    await adminApi.activateLLMConfig(id)
    await fetchConfigs()
  } catch (e: any) {
    alert(e.message)
  }
}

async function handleKnowledgeUpload() {
  const files = knowledgeFileInput.value?.files
  if (!files || files.length === 0) return
  uploading.value = true
  try {
    await knowledgeStore.upload(Array.from(files))
    knowledgeFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-10">
    <h1 class="mb-8 text-2xl font-bold text-gray-900">{{ t('admin.title') }}</h1>

    <!-- 口令校验 -->
    <div v-if="!verified" class="card">
      <p class="mb-4 text-gray-600">{{ t('admin.enterPassword') }}</p>
      <div class="flex gap-2">
        <input
          v-model="password"
          type="password"
          @keydown.enter="verify"
          :placeholder="t('admin.password')"
          class="flex-1 rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button @click="verify" class="btn-primary !px-5 !py-2 text-sm">
          {{ t('common.confirm') }}
        </button>
      </div>
    </div>

    <div v-else class="space-y-6">
      <!-- 知识库管理 -->
      <div class="card">
        <h2 class="mb-4 text-lg font-semibold text-gray-800">{{ t('home.knowledgeMgmt') }}</h2>
        <input ref="knowledgeFileInput" type="file" accept=".md" multiple class="hidden" @change="handleKnowledgeUpload" />
        <button
          @click="knowledgeFileInput?.click()"
          :disabled="uploading"
          class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-6 text-sm text-primary-600 transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
        >
          {{ uploading ? t('common.uploading') : t('home.uploadMd') }}
        </button>

        <div v-if="knowledgeStore.docs.length === 0" class="mt-3 text-sm text-gray-400">{{ t('home.noDocs') }}</div>
        <div v-else class="mt-3 space-y-2">
          <div
            v-for="doc in knowledgeStore.docs"
            :key="doc.id"
            class="flex items-center justify-between rounded-lg bg-primary-50/50 px-3 py-2"
          >
            <div>
              <p class="text-sm font-medium text-gray-700">{{ doc.title || doc.filename }}</p>
              <p class="text-xs text-gray-400">
                {{ doc.position || '-' }} ·
                {{ doc.difficulty || '-' }} ·
                <span :class="{
                  'text-yellow-500': doc.status === 'processing',
                  'text-green-500': doc.status === 'ready',
                  'text-red-500': doc.status === 'failed',
                }">{{ doc.status }}</span>
              </p>
            </div>
            <button @click="knowledgeStore.remove(doc.id)" class="text-sm text-red-400 transition hover:text-red-600">
              {{ t('common.delete') }}
            </button>
          </div>
        </div>
      </div>

      <!-- LLM 配置 -->
      <div class="card">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-gray-800">{{ t('admin.llmConfig') }}</h2>
          <button
            @click="showAddForm = !showAddForm"
            class="rounded-lg bg-gradient-brand px-4 py-2 text-sm text-white shadow-soft transition hover:brightness-110"
          >
            {{ showAddForm ? t('common.cancel') : t('admin.addNew') }}
          </button>
        </div>

        <div v-if="showAddForm" class="mb-4 space-y-3 rounded-xl bg-primary-50/50 p-4">
          <input v-model="newName" :placeholder="t('admin.configName')" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
          <input v-model="newBaseUrl" placeholder="Base URL" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
          <input v-model="newApiKey" type="password" placeholder="API Key" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
          <input v-model="newModel" placeholder="Model" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
          <button @click="addConfig" class="w-full rounded-lg bg-green-600 px-4 py-2 text-sm text-white transition hover:bg-green-700">
            {{ t('common.save') }}
          </button>
        </div>

        <div v-if="loading" class="text-center text-gray-400">{{ t('common.loading') }}</div>
        <div v-else-if="configs.length === 0" class="text-center text-sm text-gray-400">{{ t('admin.noConfigs') }}</div>
        <div v-else class="space-y-2">
          <div
            v-for="cfg in configs"
            :key="cfg.id"
            class="flex items-center justify-between rounded-lg bg-primary-50/50 px-4 py-3"
          >
            <div>
              <p class="font-medium text-gray-700">
                {{ cfg.name }}
                <span v-if="cfg.isActive" class="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">{{ t('admin.active') }}</span>
              </p>
              <p class="text-xs text-gray-400">{{ cfg.baseUrl }} · {{ cfg.model }} · {{ cfg.apiKeyMasked }}</p>
            </div>
            <button
              v-if="!cfg.isActive"
              @click="activate(cfg.id)"
              class="rounded-lg bg-gradient-brand px-3 py-1.5 text-xs text-white transition hover:brightness-110"
            >
              {{ t('admin.activate') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
