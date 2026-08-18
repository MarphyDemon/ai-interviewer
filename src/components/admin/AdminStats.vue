<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as adminApi from '@/api/admin'

const stats = ref<adminApi.PlatformStats>({
  totalUsers: 0,
  totalAdmins: 0,
  totalInterviews: 0,
  totalReports: 0,
  totalKnowledgeDocs: 0,
  totalKnowledgeVersions: 0,
  freePlanUsers: 0,
  standardPlanUsers: 0,
  enterprisePlanUsers: 0,
})

onMounted(() => {
  fetchStats()
})

async function fetchStats() {
  try {
    stats.value = await adminApi.getPlatformStats()
  } catch {
    // ignore
  }
}
</script>

<template>
  <div class="card space-y-4">
    <h2 class="text-lg font-semibold text-gray-800">📊 数据看板</h2>
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <div class="rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalUsers }}</div>
        <div class="text-xs opacity-80">总用户数</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalAdmins }}</div>
        <div class="text-xs opacity-80">管理员数</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-green-500 to-green-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalInterviews }}</div>
        <div class="text-xs opacity-80">面试总数</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalReports }}</div>
        <div class="text-xs opacity-80">报告总数</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-teal-500 to-teal-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalKnowledgeDocs }}</div>
        <div class="text-xs opacity-80">知识文档</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-pink-500 to-pink-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.totalKnowledgeVersions }}</div>
        <div class="text-xs opacity-80">版本总数</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.freePlanUsers }}</div>
        <div class="text-xs opacity-80">免费版用户</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 p-4 text-white">
        <div class="text-2xl font-bold">{{ stats.standardPlanUsers + stats.enterprisePlanUsers }}</div>
        <div class="text-xs opacity-80">付费版用户</div>
      </div>
    </div>
  </div>
</template>
