<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNav from '@/components/common/AppNav.vue'
import MobileTabBar from '@/components/common/MobileTabBar.vue'
import { useUserStore } from '@/stores/user'
import { useDevice } from '@/composables/useDevice'

const route = useRoute()
const userStore = useUserStore()
const { isMobile } = useDevice()

const showNav = computed(() => !route.meta.bare && !isMobile.value)
const showTabBar = computed(() => isMobile.value && !route.meta.bare)

onMounted(async () => {
  await userStore.initTokenFromStorage()
  if (userStore.isLoggedIn) userStore.fetchMe()
})
</script>

<template>
  <div class="min-h-screen bg-gradient-brand-soft">
    <AppNav v-if="showNav" />
    <RouterView />
    <MobileTabBar v-if="showTabBar" />
  </div>
</template>