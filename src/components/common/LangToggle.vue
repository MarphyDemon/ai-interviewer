<script setup lang="ts">
import { ref } from 'vue'
import { setLanguage, getLanguage } from '@/i18n'

const current = ref(getLanguage())

function toggle() {
  const next = current.value === 'en' ? 'zh' : 'en'
  current.value = next
  setLanguage(next)
}
</script>

<template>
  <button
    @click="toggle"
    class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 transition"
  >
    {{ current === 'en' ? '中文' : 'English' }}
  </button>
</template>
