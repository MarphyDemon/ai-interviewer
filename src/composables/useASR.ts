import { ref } from 'vue'
import type { ASRProvider } from '@/providers/asrProvider'
import type { ASRResult } from '@/types'

export function useASR(provider: ASRProvider | null) {
  const isListening = ref(false)
  const transcript = ref('')
  const partialTranscript = ref('')

  function start(onFinal?: (text: string) => void) {
    if (!provider || !provider.isAvailable()) {
      console.warn('[ASR] not available')
      return
    }

    transcript.value = ''
    partialTranscript.value = ''
    isListening.value = true

    provider.start((result: ASRResult) => {
      if (result.isFinal) {
        transcript.value += result.text
        partialTranscript.value = ''
        onFinal?.(transcript.value)
      } else {
        partialTranscript.value = result.text
      }
    })
  }

  function stop() {
    if (!provider) return
    provider.stop()
    isListening.value = false
  }

  return { isListening, transcript, partialTranscript, start, stop }
}
