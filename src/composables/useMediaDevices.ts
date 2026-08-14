import { ref, onUnmounted } from 'vue'
import { detectHost } from '@/utils/bridge'

export type DeviceStatus = 'idle' | 'loading' | 'ok' | 'denied' | 'error'

export function useMediaDevices() {
  const videoRef = ref<HTMLVideoElement | null>(null)
  const stream = ref<MediaStream | null>(null)
  const cameraStatus = ref<DeviceStatus>('idle')
  const micStatus = ref<DeviceStatus>('idle')
  const micLevel = ref(0)
  const errorMsg = ref('')

  let audioCtx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let rafId: number | null = null

  async function startCamera(): Promise<boolean> {
    cameraStatus.value = 'loading'
    try {
      const constraints: MediaStreamConstraints = {
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      }
      const host = detectHost()
      
      if (host === 'capacitor' && navigator.mediaDevices?.getUserMedia) {
        const videoStream = await navigator.mediaDevices.getUserMedia(constraints)
        if (!stream.value) stream.value = new MediaStream()
        videoStream.getVideoTracks().forEach((t) => stream.value!.addTrack(t))
        if (videoRef.value) {
          videoRef.value.srcObject = stream.value
        }
        cameraStatus.value = 'ok'
        return true
      }
      
      const videoStream = await navigator.mediaDevices.getUserMedia(constraints)
      if (!stream.value) stream.value = new MediaStream()
      videoStream.getVideoTracks().forEach((t) => stream.value!.addTrack(t))
      if (videoRef.value) {
        videoRef.value.srcObject = stream.value
      }
      cameraStatus.value = 'ok'
      return true
    } catch (e: any) {
      if (e?.name === 'NotAllowedError' || e?.name === 'PermissionDeniedError') {
        cameraStatus.value = 'denied'
        errorMsg.value = '摄像头权限被拒绝'
      } else {
        cameraStatus.value = 'error'
        errorMsg.value = e?.message || '摄像头启动失败'
      }
      return false
    }
  }

  async function startMic(): Promise<boolean> {
    micStatus.value = 'loading'
    try {
      const audioStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      })
      if (!stream.value) stream.value = new MediaStream()
      audioStream.getAudioTracks().forEach((t) => stream.value!.addTrack(t))

      audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const source = audioCtx.createMediaStreamSource(audioStream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)

      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        if (!analyser) return
        analyser.getByteFrequencyData(dataArray)
        let sum = 0
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i]
        const avg = Math.round((sum / dataArray.length / 255) * 100)
        micLevel.value = Math.min(100, avg * 2.5)
        rafId = requestAnimationFrame(tick)
      }
      tick()

      micStatus.value = 'ok'
      return true
    } catch (e: any) {
      if (e?.name === 'NotAllowedError' || e?.name === 'PermissionDeniedError') {
        micStatus.value = 'denied'
        errorMsg.value = '麦克风权限被拒绝'
      } else {
        micStatus.value = 'error'
        errorMsg.value = e?.message || '麦克风启动失败'
      }
      return false
    }
  }

  async function startAll(): Promise<void> {
    await Promise.all([startCamera(), startMic()])
  }

  function stop() {
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (audioCtx) {
      audioCtx.close().catch(() => {})
      audioCtx = null
    }
    analyser = null
    if (stream.value) {
      stream.value.getTracks().forEach((t) => t.stop())
      stream.value = null
    }
    if (videoRef.value) {
      videoRef.value.srcObject = null
    }
    micLevel.value = 0
    cameraStatus.value = 'idle'
    micStatus.value = 'idle'
  }

  function getStream(): MediaStream | null {
    return stream.value
  }

  onUnmounted(() => {
    stop()
  })

  return {
    videoRef,
    stream,
    cameraStatus,
    micStatus,
    micLevel,
    errorMsg,
    startCamera,
    startMic,
    startAll,
    stop,
    getStream,
  }
}
