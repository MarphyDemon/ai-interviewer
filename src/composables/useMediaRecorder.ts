/**
 * 媒体录制 composable（基于 MediaRecorder API）。
 * 用于面试中录制音频/视频，支持分段上传和录制状态管理。
 */
import { ref, computed, type Ref } from 'vue'
import { uploadRecording } from '@/api/recordings'

export interface UseRecorderOptions {
  /** 录制流类型 */
  streamType?: 'audio' | 'video'
  /** 录制时间片（ms），每段自动上传 */
  timeslice?: number
}

export type RecorderState = 'idle' | 'starting' | 'recording' | 'stopped' | 'error'

export function useMediaRecorder(interviewId: Ref<number | null>, options: UseRecorderOptions = {}) {
  const { streamType = 'audio', timeslice = 0 } = options

  const state = ref<RecorderState>('idle')
  const errorMsg = ref('')
  const durationMs = ref(0)
  const mediaRecorder = ref<MediaRecorder | null>(null)
  const mediaStream = ref<MediaStream | null>(null)
  const chunks = ref<Blob[]>([])
  const uploadedRecordings = ref<{ id: number; url: string }[]>([])
  let startTime = 0
  let timer: ReturnType<typeof setInterval> | null = null

  const isRecording = computed(() => state.value === 'recording')
  const canStart = computed(() => state.value === 'idle' || state.value === 'stopped')

  async function start() {
    if (!interviewId.value) {
      errorMsg.value = '请先开始面试'
      return
    }
    if (!canStart.value) return

    state.value = 'starting'
    errorMsg.value = ''
    chunks.value = []
    uploadedRecordings.value = []

    try {
      const constraints: MediaStreamConstraints = {
        audio: { echoCancellation: true, noiseSuppression: true },
      }
      if (streamType === 'video') {
        constraints.video = { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
      }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      mediaStream.value = stream

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.value.push(event.data)
        }
      }

      recorder.onstop = () => {
        stopTimer()
        durationMs.value = Date.now() - startTime
        state.value = 'stopped'
        // 释放流
        stream.getTracks().forEach((t) => t.stop())
        mediaStream.value = null
      }

      recorder.onerror = () => {
        state.value = 'error'
        errorMsg.value = '录制出错'
        stopTimer()
      }

      mediaRecorder.value = recorder
      startTime = Date.now()
      recorder.start(timeslice || undefined)
      state.value = 'recording'

      // 计时器
      timer = setInterval(() => {
        durationMs.value = Date.now() - startTime
      }, 1000)
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.name === 'NotAllowedError'
        ? '麦克风权限被拒绝'
        : e.name === 'NotFoundError'
          ? '未找到麦克风设备'
          : `启动录制失败: ${e.message}`
    }
  }

  function stop() {
    const recorder = mediaRecorder.value
    if (recorder && recorder.state === 'recording') {
      recorder.stop()
    }
  }

  /** 上传当前录制的所有片段 */
  async function flush() {
    if (chunks.value.length === 0 || !interviewId.value) return

    const fullBlob = new Blob(chunks.value, { type: chunks.value[0].type })
    chunks.value = []
    try {
      const res = await uploadRecording(interviewId.value, fullBlob, streamType)
      uploadedRecordings.value.push({ id: res.id, url: res.url })
      return res
    } catch (e: any) {
      errorMsg.value = `上传失败: ${e.message}`
      return null
    }
  }

  function stopTimer() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function reset() {
    stop()
    state.value = 'idle'
    errorMsg.value = ''
    durationMs.value = 0
    chunks.value = []
    uploadedRecordings.value = []
    stopTimer()
    if (mediaStream.value) {
      mediaStream.value.getTracks().forEach((t) => t.stop())
      mediaStream.value = null
    }
    mediaRecorder.value = null
  }

  return {
    state,
    errorMsg,
    durationMs,
    isRecording,
    canStart,
    uploadedRecordings,
    start,
    stop,
    flush,
    reset,
  }
}