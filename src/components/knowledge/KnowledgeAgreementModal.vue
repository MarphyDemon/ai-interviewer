<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'agree'): void
}>()

const { t } = useI18n()
const agreed = ref(false)

function handleAgree() {
  if (!agreed.value) return
  emit('agree')
}

function handleClose() {
  agreed.value = false
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="handleClose"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white shadow-xl max-h-[85vh] flex flex-col">
        <div class="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 class="text-lg font-semibold text-gray-800">{{ t('knowledge.agreement.title') }}</h2>
          <button
            @click="handleClose"
            class="text-gray-400 transition hover:text-gray-600"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="px-6 py-4 overflow-y-auto flex-1">
          <div class="whitespace-pre-line text-sm leading-relaxed text-gray-600">
            {{ t('knowledge.agreement.content') }}
          </div>
        </div>

        <div class="border-t border-gray-100 px-6 py-4 space-y-3">
          <label class="flex items-center gap-2 cursor-pointer select-none">
            <input
              v-model="agreed"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span class="text-sm text-gray-700">{{ t('knowledge.agreement.checkbox') }}</span>
          </label>

          <div class="flex gap-3">
            <button
              @click="handleClose"
              class="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-700 transition hover:bg-gray-50"
            >
              {{ t('knowledge.agreement.cancel') }}
            </button>
            <button
              @click="handleAgree"
              :disabled="!agreed"
              class="flex-1 rounded-xl bg-gradient-brand px-4 py-2.5 text-sm font-medium text-white shadow-soft transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ t('knowledge.agreement.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>