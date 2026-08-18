<script setup lang="ts">
import { computed, onMounted, watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNav from '@/components/common/AppNav.vue'
import MobileTabBar from '@/components/common/MobileTabBar.vue'
import { useUserStore } from '@/stores/user'
import { useDevice } from '@/composables/useDevice'
import { detectHost } from '@/utils/bridge'

const route = useRoute()
const userStore = useUserStore()
const { isMobile } = useDevice()

const showNav = computed(() => !route.meta.bare && !isMobile.value)
const showTabBar = computed(() => isMobile.value && !route.meta.bare)

const host = detectHost()

onMounted(async () => {
  await userStore.initTokenFromStorage()
  if (userStore.isLoggedIn) userStore.fetchMe()
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
    <RouterView />
    <MobileTabBar v-if="showTabBar" />
  </div>
</template>