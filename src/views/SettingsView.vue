<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import * as settingsApi from '@/api/settings'
import * as adminApi from '@/api/admin'
import type { NotificationSettings, UserQuota } from '@/types'
import type { UserListItem } from '@/api/admin'

const userStore = useUserStore()

const activeTab = ref<'personal' | 'platform'>('personal')
const isSaving = ref(false)

// Personal settings
const personal = ref<{
  preferredAvatarConfigId: number | null
  preferredPosition: string
  language: 'zh' | 'en'
  theme: 'light' | 'dark'
  notificationSettings: NotificationSettings
  quota: UserQuota | null
}>({
  preferredAvatarConfigId: null,
  preferredPosition: '',
  language: 'zh',
  theme: 'light',
  notificationSettings: { collaboration: true, review: true, system: true },
  quota: null,
})

// Admin: users management
const users = ref<UserListItem[]>([])
const showPromoteModal = ref(false)
const promoteTarget = ref<UserListItem | null>(null)
const promoteRole = ref<'user' | 'admin'>('user')

// Admin: stats
const stats = ref<adminApi.PlatformStats | null>(null)

const isAdmin = computed(() => userStore.isAdmin)

const notifItems: { key: keyof NotificationSettings; label: string }[] = [
  { key: 'collaboration', label: '协作通知（协作者编辑提醒）' },
  { key: 'review', label: '审核通知（文档审核结果）' },
  { key: 'system', label: '系统公告（版本更新等）' },
]

const positions = ['', '前端', '后端', '算法', '产品', '测试', '测试开发', '运维']

// 邀请码兑换
const inviteCodeInput = ref('')
const redeemLoading = ref(false)
const redeemMessage = ref('')
const redeemSuccess = ref(false)

// 管理员：邀请码管理
const inviteCodes = ref<adminApi.InviteCodeItem[]>([])
const newInvitePlan = ref('standard')
const newInviteMaxUses = ref(10)
const newInviteNote = ref('')

async function loadInviteCodes() {
  try {
    inviteCodes.value = await adminApi.getInviteCodes()
  } catch {}
}

async function handleCreateInviteCode() {
  try {
    const res = await adminApi.createInviteCode({
      plan: newInvitePlan.value,
      maxUses: newInviteMaxUses.value,
      note: newInviteNote.value || undefined,
    })
    alert(`邀请码生成成功: ${res.code}`)
    newInviteNote.value = ''
    await loadInviteCodes()
  } catch (e: any) {
    alert(e?.response?.data?.detail || '生成失败')
  }
}

async function handleRedeem() {
  const code = inviteCodeInput.value.trim().toUpperCase()
  if (!code) return
  redeemLoading.value = true
  redeemMessage.value = ''
  try {
    const res = await adminApi.redeemInviteCode(code)
    redeemSuccess.value = true
    redeemMessage.value = `兑换成功！您的账户已升级为${res.plan === 'standard' ? '标准版' : '企业版'}`
    inviteCodeInput.value = ''
    await loadPersonal()
  } catch (e: any) {
    redeemSuccess.value = false
    redeemMessage.value = e?.response?.data?.detail || '兑换失败，请检查邀请码是否正确'
  } finally {
    redeemLoading.value = false
  }
}

async function loadPersonal() {
  try {
    const data = await settingsApi.getPersonalSettings()
    personal.value = data
  } catch (e) {
    console.error('加载设置失败', e)
  }
}

async function savePersonal() {
  isSaving.value = true
  try {
    await settingsApi.updatePersonalSettings({
      preferredAvatarConfigId: personal.value.preferredAvatarConfigId,
      preferredPosition: personal.value.preferredPosition,
      language: personal.value.language,
      theme: personal.value.theme,
      notificationSettings: personal.value.notificationSettings,
    })
    await userStore.fetchMe()
  } catch (e) {
    console.error('保存设置失败', e)
  } finally {
    isSaving.value = false
  }
}

async function loadUsers() {
  try {
    users.value = await adminApi.getUsers()
  } catch (e) {
    console.error('加载用户列表失败', e)
  }
}

async function loadStats() {
  try {
    stats.value = await adminApi.getPlatformStats()
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

function openPromoteModal(user: UserListItem) {
  promoteTarget.value = user
  promoteRole.value = user.role
  showPromoteModal.value = true
}

async function confirmPromote() {
  if (!promoteTarget.value) return
  await adminApi.promoteUser(promoteTarget.value.id, promoteRole.value)
  showPromoteModal.value = false
  await loadUsers()
}

onMounted(async () => {
  await loadPersonal()
  if (isAdmin.value) {
    await Promise.all([loadUsers(), loadStats(), loadInviteCodes()])
  }
})
</script>

<template>
  <div class="max-w-4xl mx-auto p-4 md:p-6">
    <h1 class="text-2xl md:text-3xl font-bold text-gray-900 mb-6">设置</h1>

    <!-- Tab 切换 -->
    <div class="flex border-b border-gray-200 mb-6">
      <button
        @click="activeTab = 'personal'"
        :class="[
          'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'personal'
            ? 'border-blue-600 text-blue-600'
            : 'border-transparent text-gray-500 hover:text-gray-700',
        ]"
      >
        个人设置
      </button>
      <button
        v-if="isAdmin"
        @click="activeTab = 'platform'"
        :class="[
          'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'platform'
            ? 'border-blue-600 text-blue-600'
            : 'border-transparent text-gray-500 hover:text-gray-700',
        ]"
      >
        平台管理
      </button>
    </div>

    <!-- 个人设置 -->
    <div v-if="activeTab === 'personal'" class="space-y-6">
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">偏好设置</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">默认岗位方向</label>
            <select
              v-model="personal.preferredPosition"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option v-for="p in positions" :key="p" :value="p">
                {{ p || '未设置' }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">语言</label>
            <div class="flex gap-2">
              <button
                v-for="lang in [{ code: 'zh', label: '中文' }, { code: 'en', label: 'English' }]"
                :key="lang.code"
                @click="personal.language = lang.code as 'zh' | 'en'"
                :class="[
                  'px-4 py-2 rounded-lg text-sm font-medium border transition-colors',
                  personal.language === lang.code
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50',
                ]"
              >
                {{ lang.label }}
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">主题</label>
            <div class="flex gap-2">
              <button
                v-for="theme in [{ code: 'light', label: '☀️ 亮色' }, { code: 'dark', label: '🌙 暗色' }]"
                :key="theme.code"
                @click="personal.theme = theme.code as 'light' | 'dark'"
                :class="[
                  'px-4 py-2 rounded-lg text-sm font-medium border transition-colors',
                  personal.theme === theme.code
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50',
                ]"
              >
                {{ theme.label }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">通知设置</h2>
        <div class="space-y-3">
          <label
            v-for="item in notifItems"
            :key="item.key"
            class="flex items-center justify-between py-2"
          >
            <span class="text-sm text-gray-700">{{ item.label }}</span>
            <button
              @click="personal.notificationSettings[item.key] = !personal.notificationSettings[item.key]"
              :class="[
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                personal.notificationSettings[item.key] ? 'bg-blue-600' : 'bg-gray-300',
              ]"
            >
              <span
                :class="[
                  'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                  personal.notificationSettings[item.key] ? 'translate-x-6' : 'translate-x-1',
                ]"
              />
            </button>
          </label>
        </div>
      </section>

      <section v-if="personal.quota" class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">使用配额</h2>
        <div class="grid grid-cols-3 gap-4">
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.interviewUsed }} / {{ personal.quota.interviewLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">面试次数</div>
          </div>
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.knowledgeUsed }} / {{ personal.quota.knowledgeLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">知识库文档</div>
          </div>
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.aiCallsUsed }} / {{ personal.quota.aiCallsLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">AI 调用额度</div>
          </div>
        </div>
        <div class="mt-3 text-center">
          <span class="inline-block px-3 py-1 rounded-full text-xs font-medium"
            :class="{
              'bg-green-100 text-green-700': personal.quota.plan === 'free',
              'bg-blue-100 text-blue-700': personal.quota.plan === 'standard',
              'bg-purple-100 text-purple-700': personal.quota.plan === 'enterprise',
            }">
            {{ personal.quota.plan === 'free' ? '免费版' : personal.quota.plan === 'standard' ? '标准版' : '企业版' }}
          </span>
        </div>
      </section>

      <div class="flex justify-end">
        <button
          @click="savePersonal"
          :disabled="isSaving"
          class="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {{ isSaving ? '保存中...' : '保存设置' }}
        </button>
      </div>

      <!-- 邀请码兑换 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">邀请码兑换</h2>
        <div class="flex gap-2">
          <input v-model="inviteCodeInput" placeholder="输入邀请码"
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 uppercase" />
          <button @click="handleRedeem" :disabled="!inviteCodeInput.trim() || redeemLoading"
            class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {{ redeemLoading ? '兑换中...' : '兑换' }}
          </button>
        </div>
        <p v-if="redeemMessage" :class="['mt-2 text-sm', redeemSuccess ? 'text-green-600' : 'text-red-600']">
          {{ redeemMessage }}
        </p>
        <p class="text-xs text-gray-400 mt-2">使用邀请码可升级账户套餐，解锁更多面试次数和 AI 调用额度。</p>
      </section>
    </div>

    <!-- 平台管理 -->
    <div v-if="activeTab === 'platform' && isAdmin" class="space-y-6">
      <!-- 统计看板 -->
      <section v-if="stats" class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">平台概览</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="p-3 bg-blue-50 rounded-lg">
            <div class="text-xl font-bold text-blue-900">{{ stats.totalUsers }}</div>
            <div class="text-xs text-blue-600">总用户数</div>
          </div>
          <div class="p-3 bg-green-50 rounded-lg">
            <div class="text-xl font-bold text-green-900">{{ stats.totalInterviews }}</div>
            <div class="text-xs text-green-600">总面试数</div>
          </div>
          <div class="p-3 bg-purple-50 rounded-lg">
            <div class="text-xl font-bold text-purple-900">{{ stats.totalKnowledgeDocs }}</div>
            <div class="text-xs text-purple-600">知识文档</div>
          </div>
          <div class="p-3 bg-orange-50 rounded-lg">
            <div class="text-xl font-bold text-orange-900">{{ stats.totalReports }}</div>
            <div class="text-xs text-orange-600">面试报告</div>
          </div>
        </div>
        <div class="mt-4 flex gap-4 text-sm">
          <span class="text-gray-600">免费版: {{ stats.freePlanUsers }}</span>
          <span class="text-gray-600">标准版: {{ stats.standardPlanUsers }}</span>
          <span class="text-gray-600">企业版: {{ stats.enterprisePlanUsers }}</span>
        </div>
      </section>

      <!-- 用户管理 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">用户管理</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase">
                <th class="pb-2">用户名</th>
                <th class="pb-2">角色</th>
                <th class="pb-2">套餐</th>
                <th class="pb-2">注册时间</th>
                <th class="pb-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id" class="border-b border-gray-100">
                <td class="py-3 font-medium text-gray-900">{{ u.username }}</td>
                <td class="py-3">
                  <span class="px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'">
                    {{ u.role === 'admin' ? '管理员' : '普通用户' }}
                  </span>
                </td>
                <td class="py-3 text-gray-600">{{ u.plan }}</td>
                <td class="py-3 text-gray-500">{{ new Date(u.createdAt).toLocaleDateString('zh-CN') }}</td>
                <td class="py-3">
                  <button
                    @click="openPromoteModal(u)"
                    class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    {{ u.role === 'admin' ? '降级' : '提升' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 邀请码管理 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900">邀请码管理</h2>
          <button @click="loadInviteCodes" class="text-sm text-blue-600 hover:text-blue-800">刷新</button>
        </div>
        <div class="flex gap-2 mb-4">
          <select v-model="newInvitePlan" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="standard">标准版</option>
            <option value="enterprise">企业版</option>
          </select>
          <input v-model.number="newInviteMaxUses" type="number" min="1" max="1000" placeholder="最大使用次数"
            class="w-32 border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <input v-model="newInviteNote" placeholder="备注（可选）"
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <button @click="handleCreateInviteCode"
            class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            生成
          </button>
        </div>
        <div v-if="inviteCodes.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase">
                <th class="pb-2">邀请码</th>
                <th class="pb-2">套餐</th>
                <th class="pb-2">使用次数</th>
                <th class="pb-2">状态</th>
                <th class="pb-2">过期时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in inviteCodes" :key="c.id" class="border-b border-gray-100">
                <td class="py-3 font-mono text-gray-900">{{ c.code }}</td>
                <td class="py-3">
                  <span class="px-2 py-0.5 rounded-full text-xs"
                    :class="c.plan === 'enterprise' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'">
                    {{ c.plan === 'standard' ? '标准版' : '企业版' }}
                  </span>
                </td>
                <td class="py-3 text-gray-600">{{ c.usedCount }} / {{ c.maxUses }}</td>
                <td class="py-3">
                  <span :class="c.isActive ? 'text-green-600' : 'text-gray-400'">
                    {{ c.isActive ? '活跃' : '已失效' }}
                  </span>
                </td>
                <td class="py-3 text-gray-500">{{ c.expiresAt ? new Date(c.expiresAt).toLocaleDateString('zh-CN') : '永不过期' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="text-center py-4 text-gray-500 text-sm">暂无邀请码</div>
      </section>
    </div>

    <!-- 提升角色弹窗 -->
    <div v-if="showPromoteModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showPromoteModal = false">
      <div class="bg-white rounded-xl p-6 w-full max-w-sm mx-4">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">修改用户角色</h3>
        <p class="text-sm text-gray-600 mb-4">
          用户 <strong>{{ promoteTarget?.username }}</strong> 当前角色: {{ promoteTarget?.role === 'admin' ? '管理员' : '普通用户' }}
        </p>
        <div class="space-y-2 mb-6">
          <label
            v-for="r in [{ v: 'user', label: '普通用户' }, { v: 'admin', label: '管理员' }]"
            :key="r.v"
            class="flex items-center gap-2 p-3 border rounded-lg cursor-pointer transition-colors"
            :class="promoteRole === r.v ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'"
          >
            <input type="radio" :value="r.v" v-model="promoteRole" class="text-blue-600" />
            <span class="text-sm text-gray-700">{{ r.label }}</span>
          </label>
        </div>
        <div class="flex gap-2 justify-end">
          <button @click="showPromoteModal = false" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
            取消
          </button>
          <button @click="confirmPromote" class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            确认
          </button>
        </div>
      </div>
    </div>
  </div>
</template>