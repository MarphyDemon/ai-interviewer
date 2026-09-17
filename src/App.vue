<script setup lang="ts">
import { computed, onMounted, ref, watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppNav from '@/components/common/AppNav.vue'
import MobileTabBar from '@/components/common/MobileTabBar.vue'
import { useUserStore } from '@/stores/user'
import { useDevice } from '@/composables/useDevice'
import { detectHost } from '@/utils/bridge'
import { getRuntimeMode, type RuntimeModeResponse } from '@/api/settings'

const route = useRoute()
const userStore = useUserStore()
const { isMobile } = useDevice()
const { t } = useI18n()

const showNav = computed(() => !route.meta.bare && !isMobile.value)
const showTabBar = computed(() => isMobile.value && !route.meta.bare)

const host = detectHost()

/** 运行模式提示：云端凭证模式不提示，其余模式说明能力边界 */
const runtimeMode = ref<RuntimeModeResponse['mode'] | null>(null)
const modeHint = computed(() => {
  switch (runtimeMode.value) {
    case 'offline':
      return t('common.runtimeMode.offline')
    case 'local-llm':
      return t('common.runtimeMode.localLlm')
    case 'unconfigured':
      return t('common.runtimeMode.unconfigured')
    default:
      return ''
  }
})

onMounted(async () => {
  await userStore.initTokenFromStorage()
  if (userStore.isLoggedIn) userStore.fetchMe()
  try {
    runtimeMode.value = (await getRuntimeMode()).mode
  } catch {
    // 后端不可用时静默忽略，不阻塞页面
  }
})

watchEffect(() => {
  const body = document.body
  body.classList.toggle('wx-env', host === 'miniprogram')
  body.classList.toggle('capacitor-env', host === 'capacitor')
})
</script>

<template>
  <div class="min-h-screen bg-gradient-brand-soft" :class="{ 'pb-[calc(60px+env(safe-area-inset-bottom))]': showTabBar }">
    <AppNav v-if="showNav" />
    <div v-if="modeHint" class="mx-auto max-w-6xl px-4 pt-3">
      <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
        {{ modeHint }}
      </div>
    </div>
    <RouterView />
    <MobileTabBar v-if="showTabBar" />
  </div>
</template>