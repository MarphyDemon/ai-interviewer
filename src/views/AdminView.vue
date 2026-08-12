<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as adminApi from '@/api/admin'
import LangToggle from '@/components/common/LangToggle.vue'
import type { LLMConfig } from '@/types'

const { t } = useI18n()
const verified = ref(false)
const password = ref('')
const configs = ref<LLMConfig[]>([])
const loading = ref(false)

const showAddForm = ref(false)
const newName = ref('')
const newBaseUrl = ref('https://api.deepseek.com')
const newApiKey = ref('')
const newModel = ref('deepseek-chat')

onMounted(() => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    verified.value = true
    fetchConfigs()
  }
})

async function verify() {
  try {
    const res = await adminApi.verifyAdmin(password.value)
    localStorage.setItem('admin_token', res.token)
    verified.value = true
    fetchConfigs()
  } catch (e: any) {
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
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <div class="mx-auto max-w-2xl px-4 py-8">
      <div class="mb-6 flex items-center justify-end">
        <LangToggle />
      </div>
      <h1 class="mb-6 text-2xl font-bold text-gray-800">{{ t('admin.title') }}</h1>

      <div v-if="!verified" class="rounded-lg bg-white p-6 shadow-sm">
        <p class="mb-4 text-gray-600">{{ t('admin.enterPassword') }}</p>
        <div class="flex gap-2">
          <input
            v-model="password"
            type="password"
            @keydown.enter="verify"
            :placeholder="t('admin.password')"
            class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            @click="verify"
            class="rounded-lg bg-primary-600 px-6 py-2 text-white text-sm hover:bg-primary-700"
          >
            {{ t('common.confirm') }}
          </button>
        </div>
      </div>

      <div v-else class="space-y-4">
        <div class="rounded-lg bg-white p-6 shadow-sm">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-gray-700">{{ t('admin.llmConfig') }}</h2>
            <button
              @click="showAddForm = !showAddForm"
              class="rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700"
            >
              {{ showAddForm ? t('common.cancel') : t('admin.addNew') }}
            </button>
          </div>

          <div v-if="showAddForm" class="mb-4 space-y-3 rounded-lg bg-gray-50 p-4">
            <input v-model="newName" :placeholder="t('admin.configName')" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
            <input v-model="newBaseUrl" placeholder="Base URL" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
            <input v-model="newApiKey" type="password" placeholder="API Key" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
            <input v-model="newModel" placeholder="Model" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
            <button @click="addConfig" class="w-full rounded-lg bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700">
              {{ t('common.save') }}
            </button>
          </div>

          <div v-if="loading" class="text-center text-gray-400">{{ t('common.loading') }}</div>
          <div v-else-if="configs.length === 0" class="text-center text-sm text-gray-400">{{ t('admin.noConfigs') }}</div>
          <div v-else class="space-y-2">
            <div
              v-for="cfg in configs"
              :key="cfg.id"
              class="flex items-center justify-between rounded-md bg-gray-50 px-4 py-3"
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
                class="rounded-lg bg-primary-600 px-3 py-1.5 text-xs text-white hover:bg-primary-700"
              >
                {{ t('admin.activate') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
