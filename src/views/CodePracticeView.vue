<script setup lang="ts">
import { ref, shallowRef, computed } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import { useI18n } from 'vue-i18n'
import {
  getLanguages,
  runCode,
  streamCodeChat,
  type LanguageItem,
  type RunResult,
  type CodeChatMessage,
} from '@/api/code'
import { renderMarkdown } from '@/utils/markdown'

const { t } = useI18n()

// ---------- 消息 ----------
const messages = ref<CodeChatMessage[]>([])
const currentAssistantMsg = ref('')
const streaming = ref(false)
let abortController: AbortController | null = null

// ---------- 聊天输入 ----------
const chatInput = ref('')
const chatInputRef = ref<HTMLTextAreaElement | null>(null)

// ---------- 配置 ----------
const difficulty = ref('中等')
const position = ref('算法')

// ---------- 编辑器 ----------
const languages = ref<LanguageItem[]>([])
const currentLang = ref('python')
const code = ref('')
const editorMount = shallowRef<any>(null)

const monacoLangMap: Record<string, string> = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  java: 'java',
  cpp: 'cpp',
  c: 'c',
  go: 'go',
  rust: 'rust',
}

// ---------- 运行/提交 ----------
const stdin = ref('')
const running = ref(false)
const submitting = ref(false)
const runResult = ref<RunResult | null>(null)

// ---------- 初始化 ----------
getLanguages().then((langs) => {
  languages.value = langs
  if (langs.length > 0) {
    currentLang.value = langs[0].id
    code.value = langs[0].template
  }
})

// ---------- 方法 ----------

function handleEditorMount(editor: any, monaco: any) {
  editorMount.value = editor
  monaco.editor.defineTheme('ai-light', {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: { 'editor.background': '#ffffff' },
  })
  monaco.editor.setTheme('ai-light')
}

/** 发送消息到 AI */
async function handleSend() {
  const msg = chatInput.value.trim()
  if (!msg || streaming.value) return

  chatInput.value = ''
  messages.value.push({ role: 'user', content: msg })
  streaming.value = true
  currentAssistantMsg.value = ''
  runResult.value = null

  abortController = new AbortController()

  try {
    const full = await streamCodeChat(
      msg,
      currentLang.value,
      code.value,
      messages.value,
      {
        difficulty: difficulty.value,
        position: position.value,
        onDelta: (delta) => {
          currentAssistantMsg.value += delta
        },
        signal: abortController.signal,
      },
    )
    messages.value.push({ role: 'assistant', content: full })
    currentAssistantMsg.value = ''
  } catch (e: any) {
    if (e.name === 'AbortError') return
    messages.value.push({ role: 'assistant', content: `错误：${e.message}` })
    currentAssistantMsg.value = ''
  } finally {
    streaming.value = false
    abortController = null
  }
}

/** 快捷出题 */
function handleGenerateProblem() {
  chatInput.value = `请出一道${difficulty.value}难度的${position.value}方向编程题`
  handleSend()
}

/** 停止 AI 回复 */
function handleStop() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  if (currentAssistantMsg.value) {
    messages.value.push({ role: 'assistant', content: currentAssistantMsg.value })
    currentAssistantMsg.value = ''
  }
  streaming.value = false
}

/** 运行代码 */
async function handleRun() {
  if (!code.value.trim() || running.value) return
  running.value = true
  runResult.value = null
  try {
    runResult.value = await runCode(currentLang.value, code.value, stdin.value)
  } catch (e: any) {
    runResult.value = {
      stdout: '',
      stderr: e.message,
      exitCode: -1,
      signal: null,
      durationMs: 0,
      compileError: '',
    }
  } finally {
    running.value = false
  }
}

/** 提交代码 + AI 评价 */
async function handleSubmit() {
  if (!code.value.trim() || submitting.value) return
  submitting.value = true
  runResult.value = null

  let result: RunResult
  try {
    result = await runCode(currentLang.value, code.value, stdin.value)
    runResult.value = result
  } catch (e: any) {
    submitting.value = false
    messages.value.push({ role: 'assistant', content: `运行失败：${e.message}` })
    return
  }
  submitting.value = false

  // 将运行结果发送给 AI 评价
  const statusText = result.exitCode === 0 ? '✅ 正常运行' : '❌ 运行异常'
  const evalMsg =
    `我提交了代码，${statusText}（exitCode: ${result.exitCode}）。` +
    `请评价我的代码，分析时间复杂度和空间复杂度，给出改进建议。\n\n` +
    `我的代码：\n\`\`\`${currentLang.value}\n${code.value}\n\`\`\`\n\n` +
    `运行输出：\n\`\`\`\n${result.stdout || '(空)'}\n\`\`\`\n` +
    (result.stderr ? `标准错误：\n\`\`\`\n${result.stderr}\n\`\`\`\n` : '')

  messages.value.push({
    role: 'user',
    content: `提交结果：${statusText}`,
  })
  streaming.value = true
  currentAssistantMsg.value = ''

  abortController = new AbortController()
  try {
    const full = await streamCodeChat(
      evalMsg,
      currentLang.value,
      code.value,
      messages.value,
      {
        difficulty: difficulty.value,
        position: position.value,
        onDelta: (delta) => {
          currentAssistantMsg.value += delta
        },
        signal: abortController.signal,
      },
    )
    messages.value.push({ role: 'assistant', content: full })
    currentAssistantMsg.value = ''
  } catch (e: any) {
    if (e.name === 'AbortError') return
    messages.value.push({ role: 'assistant', content: `评价失败：${e.message}` })
    currentAssistantMsg.value = ''
  } finally {
    streaming.value = false
    abortController = null
  }
}

// ---------- 快捷键 ----------
function onChatKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="mx-auto flex h-[calc(100vh-4rem)] max-w-7xl flex-col px-4 py-4">
    <!-- 顶部工具栏 -->
    <div class="mb-3 flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-soft">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-bold text-gray-900">代码与算法练习</h1>
        <div class="h-5 w-px bg-gray-200"></div>
        <select
          v-model="difficulty"
          class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
        >
          <option value="简单">简单</option>
          <option value="中等">中等</option>
          <option value="困难">困难</option>
        </select>
        <select
          v-model="position"
          class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
        >
          <option value="前端">前端</option>
          <option value="后端">后端</option>
          <option value="算法">算法</option>
        </select>
        <button
          class="btn-primary !px-4 !py-1.5 text-sm"
          :disabled="streaming"
          @click="handleGenerateProblem"
        >
          出题
        </button>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="currentLang"
          class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
        >
          <option v-for="lang in languages" :key="lang.id" :value="lang.id">
            {{ lang.label }}
          </option>
        </select>
        <button
          class="btn-ghost !px-4 !py-1.5 text-sm"
          :disabled="running || !code.trim()"
          @click="handleRun"
        >
          {{ running ? '运行中...' : '运行' }}
        </button>
        <button
          class="btn-primary !px-4 !py-1.5 text-sm"
          :disabled="submitting || !code.trim()"
          @click="handleSubmit"
        >
          {{ submitting ? '提交中...' : '提交评价' }}
        </button>
      </div>
    </div>

    <!-- 主体：左聊天 + 右编辑器 -->
    <div class="flex flex-1 gap-4 overflow-hidden">
      <!-- 左侧聊天区 -->
      <div class="flex w-[420px] min-w-[320px] flex-col rounded-xl bg-white shadow-soft">
        <!-- 消息列表 -->
        <div class="flex-1 space-y-3 overflow-y-auto p-4">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="flex"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
              :class="
                msg.role === 'user'
                  ? 'bg-primary-500 text-white'
                  : 'bg-gray-100 text-gray-800'
              "
            >
              <div
                v-if="msg.role === 'assistant'"
                class="markdown-body"
                v-html="renderMarkdown(msg.content)"
              ></div>
              <div v-else class="whitespace-pre-wrap">{{ msg.content }}</div>
            </div>
          </div>

          <!-- 正在流式回复 -->
          <div v-if="streaming && currentAssistantMsg" class="flex justify-start">
            <div class="max-w-[85%] rounded-2xl bg-gray-100 px-4 py-2.5 text-sm leading-relaxed text-gray-800">
              <div class="markdown-body" v-html="renderMarkdown(currentAssistantMsg)"></div>
              <span class="inline-block h-4 w-2 animate-pulse bg-primary-500"></span>
            </div>
          </div>
          <div v-else-if="streaming" class="flex justify-start">
            <div class="rounded-2xl bg-gray-100 px-4 py-2.5 text-sm text-gray-400">
              <span class="inline-block animate-pulse">AI 思考中...</span>
            </div>
          </div>

          <div v-if="messages.length === 0 && !streaming" class="py-16 text-center text-sm text-gray-400">
            <div class="mb-2 text-3xl">💻</div>
            <p>选择难度和岗位方向，点击「出题」开始练习</p>
            <p class="mt-1 text-xs text-gray-300">或直接在下方输入框中与 AI 对话</p>
          </div>
        </div>

        <!-- 聊天输入框 -->
        <div class="border-t border-gray-100 p-3">
          <div class="flex gap-2">
            <textarea
              ref="chatInputRef"
              v-model="chatInput"
              :disabled="streaming"
              rows="2"
              class="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none"
              placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
              @keydown="onChatKeydown"
            ></textarea>
            <div class="flex flex-col gap-1.5">
              <button
                v-if="streaming"
                class="btn-ghost !px-3 !py-1.5 text-sm text-red-500"
                @click="handleStop"
              >
                停止
              </button>
              <button
                v-else
                class="btn-primary !px-3 !py-1.5 text-sm"
                :disabled="!chatInput.trim()"
                @click="handleSend"
              >
                发送
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧代码区 -->
      <div class="flex flex-1 flex-col gap-3 overflow-hidden">
        <!-- Monaco 编辑器 -->
        <div class="flex-1 overflow-hidden rounded-xl bg-white shadow-soft">
          <VueMonacoEditor
            :value="code"
            :language="monacoLangMap[currentLang] || 'plaintext'"
            theme="vs"
            :options="{
              minimap: { enabled: false },
              fontSize: 14,
              tabSize: 4,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: 'on',
            }"
            @mount="handleEditorMount"
            @update:value="(val: string) => (code = val)"
          />
        </div>

        <!-- 输出面板 -->
        <div class="max-h-[240px] min-h-[140px] overflow-y-auto rounded-xl bg-white shadow-soft">
          <!-- stdin 输入 -->
          <div class="border-b border-gray-100 px-4 py-2">
            <div class="flex items-center gap-2">
              <span class="text-xs font-medium text-gray-400">stdin</span>
              <input
                v-model="stdin"
                placeholder="自定义输入..."
                class="flex-1 rounded-lg border border-gray-200 px-3 py-1 font-mono text-xs focus:border-primary-400 focus:outline-none"
              />
            </div>
          </div>

          <!-- 输出内容 -->
          <div class="p-4">
            <!-- 运行结果（含提交评价） -->
            <div v-if="runResult" class="space-y-2">
              <div v-if="runResult.compileError" class="mb-2">
                <div class="mb-1 text-xs font-semibold text-orange-600">编译错误</div>
                <pre class="overflow-x-auto rounded bg-orange-50 p-2 text-xs text-orange-800">{{ runResult.compileError }}</pre>
              </div>
              <div>
                <div class="mb-1 text-xs font-semibold text-gray-500">标准输出</div>
                <pre class="overflow-x-auto whitespace-pre-wrap rounded bg-gray-50 p-2 font-mono text-xs text-gray-800">{{ runResult.stdout || '(空)' }}</pre>
              </div>
              <div v-if="runResult.stderr">
                <div class="mb-1 text-xs font-semibold text-red-500">标准错误</div>
                <pre class="overflow-x-auto whitespace-pre-wrap rounded bg-red-50 p-2 font-mono text-xs text-red-700">{{ runResult.stderr }}</pre>
              </div>
              <div class="flex gap-4 text-xs text-gray-400">
                <span>退出码：{{ runResult.exitCode }}</span>
                <span>耗时：{{ runResult.durationMs }}ms</span>
              </div>
            </div>

            <div v-else class="py-6 text-center text-xs text-gray-400">
              点击「运行」查看代码输出，或「提交评价」获取 AI 反馈
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.markdown-body :deep(pre) {
  background: #f3f4f6;
  border-radius: 6px;
  padding: 8px 12px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}
.markdown-body :deep(code) {
  font-size: 12px;
}
.markdown-body :deep(p) {
  margin-bottom: 4px;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 16px;
  margin-bottom: 4px;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-size: inherit;
  font-weight: 600;
  margin: 8px 0 4px;
}
.markdown-body :deep(table) {
  font-size: 12px;
  border-collapse: collapse;
  margin: 4px 0;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 4px 8px;
}
</style>