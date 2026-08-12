import XingyunAvatarAgent from '@xmov/avatar/agent'
import type { AvatarProvider } from './avatarProvider'
import type { ASRResult } from '@/types'
import { getAvatarConfig } from '@/api/avatar'
import type { AvatarConfig } from '@/types'

type ASRCallback = (result: ASRResult) => void

export class DigitalAvatarProvider implements AvatarProvider {
  private agent: XingyunAvatarAgent | null = null
  private ready = false
  private asrCallback: ASRCallback | null = null
  private config: AvatarConfig | null = null

  async init(containerId: string): Promise<void> {
    this.config = await getAvatarConfig()

    const container = document.getElementById(containerId)
    if (!container) {
      throw new Error(`Container #${containerId} not found`)
    }

    this.agent = new XingyunAvatarAgent({
      containerId,
      container,
      appId: this.config.appId,
      "asr_id": 2,
      "features": {
          "anti_interference": {
              "semantic_judge_enabled": false
          },
          "speech_frontend": {
              "enabled": false,
              "enable_aec": false,
              "enable_speech_separation": false
          },
          "vad_merge_mode": true,
          "volume_and_repetition_text_detection": true
      },
      "llm_id": 2,
      appSecret: this.config.appSecret,
      gatewayServer: this.config.gatewayServer,
      onMessage: (error) => {
        console.error(
          '[Avatar] SDK message:',
          error.error_name || error.code,
          error.message,
        )
      },
      agentCallbacks: {
        onASRResult: (result) => {
          if (this.asrCallback) {
            this.asrCallback({ text: result.text, isFinal: result.isFinal })
          }
        },
        onAgentStateChange: (state) => {
          console.debug('[Avatar] agent state:', state)
        },
        onSpeakStateChange: (event) => {
          console.debug('[Avatar] speak state:', event.state)
        },
        onConversationChange: (event) => {
          console.debug('[Avatar] conversation:', event.state)
        },
        onError: (error) => {
          console.error('[Avatar] error:', error.code, error.message)
        },
      },
    })

    await this.agent.init({
      onDownloadProgress: (progress) => {
        console.debug('[Avatar] download:', Math.round(progress) + '%')
      },
    })

    this.ready = true
  }

  async speak(text: string): Promise<void> {
    if (!this.agent) throw new Error('Avatar not initialized')
    await this.agent.speakByE2E(text)
  }

  async startASR(onResult: ASRCallback): Promise<void> {
    if (!this.agent) throw new Error('Avatar not initialized')
    this.asrCallback = onResult
    await this.agent.startASR()
  }

  async stopASR(): Promise<void> {
    if (!this.agent) return
    this.asrCallback = null
    await this.agent.stopASR()
  }

  async interrupt(): Promise<void> {
    if (!this.agent) return
    await this.agent.interruptConversation()
  }

  idle(): void {
    if (this.agent) this.agent.idle()
  }

  async destroy(): Promise<void> {
    if (this.agent) {
      await this.agent.destroy()
      this.agent = null
      this.ready = false
    }
  }

  isReady(): boolean {
    return this.ready
  }
}
