<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function onSubmit() {
  errorMsg.value = ''
  if (!username.value.trim()) {
    errorMsg.value = t('register.usernameRequired')
    return
  }
  if (username.value.trim().length < 3 || username.value.trim().length > 32) {
    errorMsg.value = t('register.usernameLength')
    return
  }
  if (password.value.length < 8) {
    errorMsg.value = t('register.passwordMinLength')
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = t('register.passwordMismatch')
    return
  }
  loading.value = true
  try {
    await userStore.doRegister(username.value.trim(), password.value)
    router.replace('/setup')
  } catch (e: any) {
    errorMsg.value = e.message || t('register.registerFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="mx-auto flex min-h-[70vh] max-w-md items-center px-4 py-12">
    <div class="card w-full !p-8">
      <h1 class="text-2xl font-bold text-gray-900">{{ t('register.title') }}</h1>
      <p class="mt-2 text-sm text-gray-500">{{ t('register.subtitle') }}</p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">{{ t('register.username') }}</label>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="input"
            :placeholder="t('register.usernamePlaceholder')"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">{{ t('register.password') }}</label>
          <input
            v-model="password"
            type="password"
            autocomplete="new-password"
            class="input"
            :placeholder="t('register.passwordPlaceholder')"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">{{ t('register.confirmPassword') }}</label>
          <input
            v-model="confirmPassword"
            type="password"
            autocomplete="new-password"
            class="input"
            :placeholder="t('register.confirmPasswordPlaceholder')"
          />
        </div>

        <p v-if="errorMsg" class="text-sm text-red-500">{{ errorMsg }}</p>

        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? t('register.loading') : t('register.submit') }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-gray-500">
        {{ t('register.hasAccount') }}
        <router-link to="/login" class="font-medium text-primary-600 hover:text-primary-700">
          {{ t('register.goLogin') }}
        </router-link>
      </p>
    </div>
  </div>
</template>
