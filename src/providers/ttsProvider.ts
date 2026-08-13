export interface TTSProvider {
  speak(text: string, onEnd?: () => void): void
  /** 流式追加播报：不中断当前播报，排队等待（用于流式 TTS） */
  speakQueued?(text: string): void
  cancel(): void
  isAvailable(): boolean
}
