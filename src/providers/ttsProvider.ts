export interface TTSProvider {
  speak(text: string, onEnd?: () => void): void
  cancel(): void
  isAvailable(): boolean
}
