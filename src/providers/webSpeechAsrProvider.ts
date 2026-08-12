import type { ASRProvider } from './asrProvider'
import type { ASRResult } from '@/types'

type ASRCallback = (result: ASRResult) => void

export class WebSpeechAsrProvider implements ASRProvider {
  private recognition: any = null

  private getSpeechRecognition(): any {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition
    return SR
  }

  isAvailable(): boolean {
    return !!this.getSpeechRecognition()
  }

  start(onResult: ASRCallback): void {
    const SR = this.getSpeechRecognition()
    if (!SR) {
      console.error('[WebSpeech ASR] not supported')
      return
    }

    this.recognition = new SR()
    this.recognition.lang = 'zh-CN'
    this.recognition.continuous = true
    this.recognition.interimResults = true

    this.recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        const isFinal = event.results[i].isFinal
        onResult({ text: transcript, isFinal })
      }
    }

    this.recognition.onerror = (event: any) => {
      console.error('[WebSpeech ASR] error:', event.error)
    }

    this.recognition.onend = () => {
      console.debug('[WebSpeech ASR] ended')
    }

    this.recognition.start()
  }

  stop(): void {
    if (this.recognition) {
      this.recognition.stop()
      this.recognition = null
    }
  }
}
