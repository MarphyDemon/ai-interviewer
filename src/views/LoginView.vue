<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function onSubmit() {
  errorMsg.value = ''
  if (!username.value.trim() || !password.value) {
    errorMsg.value = t('login.usernamePasswordRequired')
    return
  }
  loading.value = true
  try {
    await userStore.doLogin(username.value.trim(), password.value)
    const redirect = (route.query.redirect as string) || '/setup'
    router.replace(redirect)
  } catch (e: any) {
    errorMsg.value = e.message || t('login.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="mx-auto flex min-h-[70vh] max-w-md items-center px-4 py-12">
    <div class="card w-full !p-8">
      <h1 class="text-2xl font-bold text-gray-900">{{ t('login.title') }}</h1>
      <p class="mt-2 text-sm text-gray-500">{{ t('login.subtitle') }}</p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">{{ t('login.username') }}</label>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="input"
            :placeholder="t('login.usernamePlaceholder')"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">{{ t('login.password') }}</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="input"
            :placeholder="t('login.passwordPlaceholder')"
          />
        </div>

        <p v-if="errorMsg" class="text-sm text-red-500">{{ errorMsg }}</p>

        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? t('login.loading') : t('login.submit') }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-gray-500">
        {{ t('login.noAccount') }}
        <router-link to="/register" class="font-medium text-primary-600 hover:text-primary-700">
          {{ t('login.registerNow') }}
        </router-link>
      </p>
    </div>
  </div>
</template>
