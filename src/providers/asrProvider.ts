import type { ASRResult } from '@/types'

export interface ASRProvider {
  start(onResult: (result: ASRResult) => void): void
  stop(): void
  isAvailable(): boolean
}
