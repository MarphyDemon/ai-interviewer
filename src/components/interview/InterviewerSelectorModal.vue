<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getHomepageAvatars, setPreferredAvatar, type HomepageAvatarItem } from '@/api/avatar'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', avatar: HomepageAvatarItem): void
}>()

const { t } = useI18n()
const avatars = ref<HomepageAvatarItem[]>([])
const loading = ref(false)
const selectedId = ref<number | null>(null)

const selectedAvatar = computed(() =>
  avatars.value.find((a) => (a.id ?? -1) === selectedId.value) ||
  avatars.value.find((a) => a.isSelected) ||
  avatars.value.find((a) => a.isDefault) ||
  avatars.value[0] || null
)

async function fetchAvatars() {
  loading.value = true
  try {
    avatars.value = await getHomepageAvatars()
    const current = avatars.value.find((a) => a.isSelected)
    if (current) {
      selectedId.value = current.id ?? null
    } else if (avatars.value.length > 0) {
      selectedId.value = avatars.value[0].id ?? null
    }
  } catch {
    avatars.value = []
  } finally {
    loading.value = false
  }
}

function selectAvatar(a: HomepageAvatarItem) {
  selectedId.value = a.id ?? null
}

async function handleConfirm() {
  const avatar = selectedAvatar.value
  if (!avatar) return
  try {
    await setPreferredAvatar(avatar.id)
    emit('confirm', avatar)
  } catch (e: any) {
    alert(e.message)
  }
}

function handleClose() {
  emit('close')
}

watch(
  () => props.visible,
  (v) => {
    if (v && avatars.value.length === 0) {
      fetchAvatars()
    }
  }
)

onMounted(() => {
  if (props.visible) {
    fetchAvatars()
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="handleClose"
    >
      <div class="w-full max-w-md rounded-2xl bg-white shadow-xl max-h-[85vh] flex flex-col">
        <div class="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div>
            <h2 class="text-lg font-semibold text-gray-800">{{ t('interviewer.selector.title') }}</h2>
            <p class="mt-0.5 text-xs text-gray-500">{{ t('interviewer.selector.subtitle') }}</p>
          </div>
          <button
            @click="handleClose"
            class="text-gray-400 transition hover:text-gray-600"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="px-4 py-4 overflow-y-auto flex-1">
          <div v-if="loading" class="flex items-center justify-center py-10">
            <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-500"></div>
          </div>

          <div v-else-if="avatars.length === 0" class="py-10 text-center text-sm text-gray-400">
            暂无可用面试官
          </div>

          <div v-else class="grid grid-cols-3 gap-3">
            <button
              v-for="a in avatars"
              :key="a.id ?? 'default'"
              @click="selectAvatar(a)"
              class="relative flex flex-col items-center gap-1.5 rounded-xl p-2 transition hover:-translate-y-0.5"
              :class="(a.id ?? -1) === selectedId ? 'bg-primary-50 ring-2 ring-primary-400' : 'hover:bg-gray-50'"
            >
              <div class="aspect-[9/16] w-full overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
                <img
                  :src="a.avatarImage"
                  :alt="a.name"
                  class="h-full w-full object-cover"
                  @error="($event) => { ($event.target as HTMLImageElement).style.display = 'none' }"
                />
              </div>
              <span class="w-full truncate text-center text-xs font-medium text-gray-700">{{ a.name }}</span>
              <span
                v-if="(a.id ?? -1) === selectedId"
                class="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary-500 text-white"
              >
                <svg viewBox="0 0 24 24" class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
            </button>
          </div>
        </div>

        <div class="border-t border-gray-100 px-6 py-4">
          <div v-if="selectedAvatar" class="mb-3 flex items-center gap-2 rounded-lg bg-primary-50/60 px-3 py-2">
            <div class="aspect-[9/16] h-12 overflow-hidden rounded-md border border-gray-200">
              <img
                :src="selectedAvatar.avatarImage"
                :alt="selectedAvatar.name"
                class="h-full w-full object-cover"
                @error="($event) => { ($event.target as HTMLImageElement).style.display = 'none' }"
              />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-700">{{ selectedAvatar.name }}</p>
              <p class="text-xs text-gray-400">{{ t('interviewer.selector.current') }}</p>
            </div>
          </div>

          <div class="flex gap-3">
            <button
              @click="handleClose"
              class="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-700 transition hover:bg-gray-50"
            >
              {{ t('interviewer.selector.cancel') }}
            </button>
            <button
              @click="handleConfirm"
              :disabled="!selectedAvatar"
              class="flex-1 rounded-xl bg-gradient-brand px-4 py-2.5 text-sm font-medium text-white shadow-soft transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ t('interviewer.selector.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>