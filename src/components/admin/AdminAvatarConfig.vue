<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as adminApi from '@/api/admin'
import type { AvatarProviderConfigItem } from '@/api/admin'

const { t } = useI18n()

const avatarConfigs = ref<AvatarProviderConfigItem[]>([])
const avatarLoading = ref(false)
const showAvatarAddForm = ref(false)
const editingAvatarId = ref<number | null>(null)
const newAvatarName = ref('')
const newAppId = ref('')
const newAppSecret = ref('')
const newGatewayServer = ref('https://test-nebula-agent.xmov.ai/user/v1/ttsa_v2/session')
const newAvatarImage = ref('')
const showAvatarSecret = ref(false)

onMounted(() => {
  fetchAvatarConfigs()
})

async function fetchAvatarConfigs() {
  avatarLoading.value = true
  try {
    avatarConfigs.value = await adminApi.getAvatarConfigs()
  } finally {
    avatarLoading.value = false
  }
}

async function saveAvatarConfig() {
  try {
    if (editingAvatarId.value !== null) {
      await adminApi.updateAvatarConfig(editingAvatarId.value, {
        name: newAvatarName.value,
        appId: newAppId.value,
        appSecret: newAppSecret.value || undefined,
        gatewayServer: newGatewayServer.value,
        avatarImage: newAvatarImage.value,
      })
    } else {
      await adminApi.createAvatarConfig({
        name: newAvatarName.value,
        appId: newAppId.value,
        appSecret: newAppSecret.value,
        gatewayServer: newGatewayServer.value,
        avatarImage: newAvatarImage.value,
      })
    }
    resetAvatarForm()
    await fetchAvatarConfigs()
  } catch (e: any) {
    alert('保存失败：' + e.message)
  }
}

function startEditAvatar(cfg: AvatarProviderConfigItem) {
  editingAvatarId.value = cfg.id
  newAvatarName.value = cfg.name
  newAppId.value = cfg.appId
  newAppSecret.value = ''
  newGatewayServer.value = cfg.gatewayServer
  newAvatarImage.value = cfg.avatarImage || ''
  showAvatarAddForm.value = true
}

function resetAvatarForm() {
  showAvatarAddForm.value = false
  editingAvatarId.value = null
  newAvatarName.value = ''
  newAppId.value = ''
  newAppSecret.value = ''
  newGatewayServer.value = 'https://test-nebula-agent.xmov.ai/user/v1/ttsa_v2/session'
  newAvatarImage.value = ''
  showAvatarSecret.value = false
}

async function toggleAvatar(id: number, currentActive: boolean) {
  try {
    if (currentActive) {
      await adminApi.deactivateAvatarConfig(id)
    } else {
      await adminApi.activateAvatarConfig(id)
    }
    await fetchAvatarConfigs()
  } catch (e: any) {
    alert(e.message)
  }
}

async function removeAvatarConfig(id: number) {
  if (!confirm(t('admin.confirmDeleteAvatar'))) return
  try {
    await adminApi.deleteAvatarConfig(id)
    if (editingAvatarId.value === id) resetAvatarForm()
    await fetchAvatarConfigs()
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div class="card space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-800">{{ t('admin.avatarConfig') }}</h2>
      <button
        @click="editingAvatarId !== null ? resetAvatarForm() : (showAvatarAddForm = !showAvatarAddForm)"
        class="rounded-lg bg-gradient-brand px-4 py-2 text-sm text-white shadow-soft transition hover:brightness-110"
      >
        {{ editingAvatarId !== null ? t('common.cancel') : showAvatarAddForm ? t('common.cancel') : t('admin.addNew') }}
      </button>
    </div>

    <div v-if="showAvatarAddForm" class="space-y-3 rounded-xl bg-primary-50/50 p-4">
      <input v-model="newAvatarName" :placeholder="t('admin.configName')" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <input v-model="newAppId" placeholder="App ID" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <div class="relative">
        <input v-model="newAppSecret" :type="showAvatarSecret ? 'text' : 'password'" :placeholder="editingAvatarId !== null ? t('admin.leaveBlank') : 'App Secret'" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 pr-16 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
        <button
          type="button"
          @click="showAvatarSecret = !showAvatarSecret"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-gray-600"
        >
          {{ showAvatarSecret ? t('common.hide') : t('common.show') }}
        </button>
      </div>
      <input v-model="newGatewayServer" placeholder="Gateway Server" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('admin.avatarImageLabel') }}</label>
        <input v-model="newAvatarImage" placeholder="https://...avatar.png" class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
        <div v-if="newAvatarImage" class="mt-2 flex items-center gap-2">
          <div class="aspect-[9/16] h-20 overflow-hidden rounded-lg border border-gray-200">
            <img :src="newAvatarImage" alt="形象预览" class="h-full w-full object-cover" @error="newAvatarImage = ''" />
          </div>
          <span class="text-xs text-gray-400">{{ t('admin.preview') }}</span>
        </div>
      </div>
      <button @click="saveAvatarConfig" class="w-full rounded-lg bg-green-600 px-4 py-2 text-sm text-white transition hover:bg-green-700">
        {{ t('common.save') }}
      </button>
    </div>

    <div v-if="avatarLoading" class="text-center text-gray-400">{{ t('common.loading') }}</div>
    <div v-else-if="avatarConfigs.length === 0" class="text-center text-sm text-gray-400">
      {{ t('admin.noConfigs') }}
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="cfg in avatarConfigs"
        :key="cfg.id"
        class="flex flex-col gap-3 rounded-lg bg-primary-50/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <div
            v-if="cfg.avatarImage"
            class="aspect-[9/16] h-16 shrink-0 overflow-hidden rounded-lg border border-gray-200"
          >
            <img
              :src="cfg.avatarImage"
              :alt="cfg.name"
              class="h-full w-full object-cover"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
            />
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate font-medium text-gray-700">
              {{ cfg.name }}
              <span v-if="cfg.isActive" class="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">{{ t('admin.showOnHomepage') }}</span>
              <span v-else class="ml-2 rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-500">{{ t('admin.hideOnHomepage') }}</span>
            </p>
            <p class="truncate text-xs text-gray-400">{{ cfg.appId }} · {{ cfg.appSecretMasked }}</p>
            <p class="truncate text-xs text-gray-400">{{ cfg.gatewayServer }}</p>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            @click="startEditAvatar(cfg)"
            class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs text-gray-600 transition hover:bg-gray-200"
          >
            {{ t('common.edit') }}
          </button>
          <button
            v-if="cfg.isActive"
            @click="toggleAvatar(cfg.id, cfg.isActive)"
            class="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-600 transition hover:bg-amber-100"
          >
            {{ t('admin.hideOnHomepage') }}
          </button>
          <button
            v-else
            @click="toggleAvatar(cfg.id, cfg.isActive)"
            class="rounded-lg bg-gradient-brand px-3 py-1.5 text-xs text-white transition hover:brightness-110"
          >
            {{ t('admin.showOnHomepage') }}
          </button>
          <button
            @click="removeAvatarConfig(cfg.id)"
            class="rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-500 transition hover:bg-red-100"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
