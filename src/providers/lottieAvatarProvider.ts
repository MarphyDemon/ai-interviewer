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

  async init(containerId: string, _brainConfig?: import('@/types').BrainConfig): Promise<void> {
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
    if (this.container) {
      const avatarEl = this.container.querySelector('.lottie-avatar')
      if (avatarEl) {
        avatarEl.classList.remove('speaking')
      }
    }
  }

  /** 流式追加播报：走 TTS 队列（不 cancel），边生成边讲 */
  startSpeakStream(): void {
    // 开始新轮次前清掉上一轮残留
    this.ttsProvider.cancel()
  }

  speakChunk(text: string): void {
    if (!this.container || !text.trim()) return
    const avatarEl = this.container.querySelector('.lottie-avatar')
    avatarEl?.classList.add('speaking')
    this.ttsProvider.speakQueued?.(text)
    // 队列播完后移除 speaking 动画（Web Speech 专有判断）
    const checkEnd = () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window && !window.speechSynthesis.speaking) {
        avatarEl?.classList.remove('speaking')
      } else {
        window.setTimeout(checkEnd, 300)
      }
    }
    window.setTimeout(checkEnd, 300)
  }

  endSpeakStream(text: string): void {
    if (text.trim()) {
      this.speakChunk(text)
    }
  }

  idle(): void {
    if (this.container) {
      const avatarEl = this.container.querySelector('.lottie-avatar')
      if (avatarEl) {
        avatarEl.classList.remove('speaking')
      }
    }
  }

  /** 降级模式无姿态体系，以下三个姿态方法均为 no-op（仅为接口对齐） */
  listen(): void {
    // no-op
  }

  think(): void {
    // no-op
  }

  interactiveIdle(): void {
    // no-op
  }

  /** Lottie 走 DOM 自适应，无需额外适配 */
  resize(): void {
    // no-op：浏览器 DOM 尺寸变化自动生效
  }

  /** Lottie 降级模式下无 SDK LLM 响应，空实现 */
  setOnLLMResponse(_callback: (response: import('@/types').AgentLLMResponse) => void): void {
    // no-op
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
