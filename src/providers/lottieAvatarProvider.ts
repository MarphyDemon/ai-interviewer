import type { AvatarProvider } from './avatarProvider'
import type { ASRResult } from '@/types'
import type { TTSProvider } from './ttsProvider'
import type { ASRProvider } from './asrProvider'

type ASRCallback = (result: ASRResult) => void

export class LottieAvatarProvider implements AvatarProvider {
  private container: HTMLElement | null = null
  private ready = false
  private ttsProvider: TTSProvider
  private asrProvider: ASRProvider

  constructor(ttsProvider: TTSProvider, asrProvider: ASRProvider) {
    this.ttsProvider = ttsProvider
    this.asrProvider = asrProvider
  }

  async init(containerId: string): Promise<void> {
    this.container = document.getElementById(containerId)
    if (!this.container) {
      throw new Error(`Container #${containerId} not found`)
    }
    this.container.innerHTML = `
      <div class="flex h-full items-center justify-center bg-gradient-to-b from-primary-50 to-primary-100">
        <div class="text-center">
          <div class="lottie-avatar mx-auto mb-4 h-32 w-32 rounded-full bg-primary-200 flex items-center justify-center">
            <div class="lottie-eyes text-4xl">😊</div>
          </div>
          <p class="text-sm text-primary-600">面试官</p>
        </div>
      </div>
    `
    this.ready = true
  }

  async speak(text: string): Promise<void> {
    if (!this.container) return
    const avatarEl = this.container.querySelector('.lottie-avatar')
    if (avatarEl) {
      avatarEl.classList.add('speaking')
    }
    return new Promise<void>((resolve) => {
      this.ttsProvider.speak(text, () => {
        if (avatarEl) {
          avatarEl.classList.remove('speaking')
        }
        resolve()
      })
    })
  }

  async startASR(onResult: ASRCallback): Promise<void> {
    this.asrProvider.start(onResult)
  }

  async stopASR(): Promise<void> {
    this.asrProvider.stop()
  }

  async interrupt(): Promise<void> {
    this.ttsProvider.cancel()
  }

  idle(): void {
    if (this.container) {
      const avatarEl = this.container.querySelector('.lottie-avatar')
      if (avatarEl) {
        avatarEl.classList.remove('speaking')
      }
    }
  }

  async destroy(): Promise<void> {
    if (this.container) {
      this.container.innerHTML = ''
      this.container = null
    }
    this.ready = false
  }

  isReady(): boolean {
    return this.ready
  }
}
