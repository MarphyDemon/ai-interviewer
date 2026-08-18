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
      "asr_config": {
        "provider": "doubao",
        "base_url": "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
        "headers": {
          "resource_id": "volc.bigasr.sauc.duration",
          "access_token": "pWWHUQiZ7HzuwkFyOt9DjXYNaDFtpJLh",
          "app_id": "6220573154"
        },
        "request": {
          "enable_ddc": false,
          "enable_itn": true,
          "model_name": "bigmodel",
          "enable_punc": true,
          "result_type": "full",
          "model_version": "400",
          "end_window_size": 200,
          "show_utterances": true,
          "force_to_speech_time": 1000
        }
      },
      "brain_config": {
        "provider": "doubao",
        "model": "ep-20260326184144-bln7r",
        "api_key": "669350ba-bc3b-4802-b252-f6213b9433bc",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3"
      },
      config: {
        init_events: [
          {
            "axis_id": 100,
            "height": 1,
            "image": "https://media.xingyun3d.com/test_0820/20250820-102325.png",
            "type": "SetCharacterCanvasAnchor",
            "width": 1,
            "x_location": 0,
            "y_location": 0
          }
        ]
      },
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

  /** 流式追加播报：按 SDK 协议发送 is_start/is_end 分帧，边生成边讲 */
  private speakStreamStarted = false

  startSpeakStream(): void {
    this.speakStreamStarted = false
  }

  speakChunk(text: string): void {
    if (!this.agent || !text.trim()) return
    const isStart = !this.speakStreamStarted
    this.speakStreamStarted = true
      // 镜像 speakByE2E 内部 sendControl，但用自定义 is_start/is_end 分帧
      ; (this.agent as any).sendControl({
        type: 'speak',
        message: { text, is_start: isStart, is_end: false },
      })
  }

  endSpeakStream(text: string): void {
    if (!this.agent) return
    const isStart = !this.speakStreamStarted
      ; (this.agent as any).sendControl({
        type: 'speak',
        message: { text: text || '', is_start: isStart, is_end: true },
      })
    this.speakStreamStarted = false
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
    this.speakStreamStarted = false
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
