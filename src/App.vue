<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNav from '@/components/common/AppNav.vue'

const route = useRoute()
const showNav = computed(() => !route.meta.bare)
</script>

<template>
  <div class="min-h-screen bg-gradient-brand-soft">
    <AppNav v-if="showNav" />
    <RouterView />
  </div>
</template>
