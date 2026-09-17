<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as adminApi from '@/api/admin'
import type { LLMConfig } from '@/types'

const { t } = useI18n()

const configs = ref<LLMConfig[]>([])
const loading = ref(false)

const showAddForm = ref(false)
const editingLlmId = ref<number | null>(null)
const newName = ref('')
const newBaseUrl = ref('https://api.deepseek.com')
const newApiKey = ref('')
const newModel = ref('deepseek-chat')

onMounted(() => {
  fetchConfigs()
})

async function fetchConfigs() {
  loading.value = true
  try {
    configs.value = await adminApi.getLLMConfigs()
  } catch {
    // 401 由 client.ts 统一派发 admin-unauthorized，AdminView 会回退到口令校验界面
    configs.value = []
  } finally {
    loading.value = false
  }
}

async function saveLlmConfig() {
  try {
    if (editingLlmId.value !== null) {
      await adminApi.updateLLMConfig(editingLlmId.value, {
        name: newName.value,
        baseUrl: newBaseUrl.value,
        apiKey: newApiKey.value || undefined,
        model: newModel.value,
      })
    } else {
      await adminApi.createLLMConfig({
        name: newName.value,
        baseUrl: newBaseUrl.value,
        apiKey: newApiKey.value,
        model: newModel.value,
      })
    }
    resetLlmForm()
    await fetchConfigs()
  } catch (e: any) {
    alert(t('admin.addFailed') + e.message)
  }
}

function startEditLlm(cfg: LLMConfig) {
  editingLlmId.value = cfg.id
  newName.value = cfg.name
  newBaseUrl.value = cfg.baseUrl
  newApiKey.value = ''
  newModel.value = cfg.model
  showAddForm.value = true
}

function resetLlmForm() {
  showAddForm.value = false
  editingLlmId.value = null
  newName.value = ''
  newBaseUrl.value = 'https://api.deepseek.com'
  newApiKey.value = ''
  newModel.value = 'deepseek-chat'
}

async function toggleLlm(id: number, currentActive: boolean) {
  try {
    if (currentActive) {
      await adminApi.deactivateLLMConfig(id)
    } else {
      await adminApi.activateLLMConfig(id)
    }
    await fetchConfigs()
  } catch (e: any) {
    alert(e.message)
  }
}

async function removeLlm(id: number) {
  if (!confirm(t('admin.confirmDeleteLlm'))) return
  try {
    await adminApi.deleteLLMConfig(id)
    if (editingLlmId.value === id) resetLlmForm()
    await fetchConfigs()
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div class="card space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-800">{{ t('admin.llmConfig') }}</h2>
      <button
        @click="editingLlmId !== null ? resetLlmForm() : (showAddForm = !showAddForm)"
        class="rounded-lg bg-gradient-brand px-4 py-2 text-sm text-white shadow-soft transition hover:brightness-110"
      >
        {{ editingLlmId !== null ? t('common.cancel') : showAddForm ? t('common.cancel') : t('admin.addNew') }}
      </button>
    </div>

    <div v-if="showAddForm" class="space-y-3 rounded-xl bg-primary-50/50 p-4">
      <input v-model="newName" :placeholder="t('admin.configName')" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <input v-model="newBaseUrl" placeholder="Base URL" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <input v-model="newApiKey" type="password" :placeholder="editingLlmId !== null ? t('admin.leaveBlank') : 'API Key'" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <input v-model="newModel" placeholder="Model" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <button @click="saveLlmConfig" class="w-full rounded-lg bg-green-600 px-4 py-2 text-sm text-white transition hover:bg-green-700">
        {{ t('common.save') }}
      </button>
    </div>

    <div v-if="loading" class="text-center text-gray-400">{{ t('common.loading') }}</div>
    <div v-else-if="configs.length === 0" class="text-center text-sm text-gray-400">{{ t('admin.noConfigs') }}</div>
    <div v-else class="space-y-2">
      <div
        v-for="cfg in configs"
        :key="cfg.id"
        class="flex flex-col gap-2 rounded-lg bg-primary-50/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate font-medium text-gray-700">
            {{ cfg.name }}
            <span v-if="cfg.isActive" class="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">{{ t('admin.active') }}</span>
            <span v-else class="ml-2 rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-500">{{ t('admin.inactive') }}</span>
          </p>
          <p class="truncate text-xs text-gray-400">{{ cfg.baseUrl }} · {{ cfg.model }} · {{ cfg.apiKeyMasked }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            @click="startEditLlm(cfg)"
            class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs text-gray-600 transition hover:bg-gray-200"
          >
            {{ t('common.edit') }}
          </button>
          <button
            v-if="cfg.isActive"
            @click="toggleLlm(cfg.id, cfg.isActive)"
            class="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-600 transition hover:bg-amber-100"
          >
            {{ t('admin.deactivate') }}
          </button>
          <button
            v-else
            @click="toggleLlm(cfg.id, cfg.isActive)"
            class="rounded-lg bg-gradient-brand px-3 py-1.5 text-xs text-white transition hover:brightness-110"
          >
            {{ t('admin.activate') }}
          </button>
          <button
            @click="removeLlm(cfg.id)"
            class="rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-500 transition hover:bg-red-100"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
