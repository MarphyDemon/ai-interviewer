import type { ASRResult } from '@/types'

export interface AvatarProvider {
  init(containerId: string): Promise<void>
  speak(text: string): Promise<void>
  startASR(onResult: (result: ASRResult) => void): Promise<void>
  stopASR(): Promise<void>
  interrupt(): Promise<void>
  idle(): void
  destroy(): Promise<void>
  isReady(): boolean
}
