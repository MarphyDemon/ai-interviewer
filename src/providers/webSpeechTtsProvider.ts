import type { TTSProvider } from './ttsProvider'

export class WebSpeechTtsProvider implements TTSProvider {
  private utterance: SpeechSynthesisUtterance | null = null

  isAvailable(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  }

  speak(text: string, onEnd?: () => void): void {
    if (!this.isAvailable()) {
      console.warn('[WebSpeech TTS] not supported')
      onEnd?.()
      return
    }

    window.speechSynthesis.cancel()

    this.utterance = new SpeechSynthesisUtterance(text)
    this.utterance.lang = 'zh-CN'
    this.utterance.rate = 1.0
    this.utterance.pitch = 1.0

    if (onEnd) {
      this.utterance.onend = onEnd
    }

    window.speechSynthesis.speak(this.utterance)
  }

  cancel(): void {
    if (this.isAvailable()) {
      window.speechSynthesis.cancel()
    }
    this.utterance = null
  }
}
