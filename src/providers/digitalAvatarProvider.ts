import XingyunAvatarAgent from '@xmov/avatar/agent'
import type { AvatarProvider, AvatarInitOptions } from './avatarProvider'
import type { AgentLLMResponse, ASRResult, BrainConfig } from '@/types'
import { getAvatarConfig } from '@/api/avatar'
import type { AvatarConfig } from '@/types'

type ASRCallback = (result: ASRResult) => void
type LLMResponseCallback = (response: AgentLLMResponse) => void

export class DigitalAvatarProvider implements AvatarProvider {
  private agent: XingyunAvatarAgent | null = null
  private ready = false
  private asrCallback: ASRCallback | null = null
  private llmResponseCallback: LLMResponseCallback | null = null
  private subtitleCallback: ((text: string | null, on: boolean) => void) | null = null
  private config: AvatarConfig | null = null
  private brainConfig: BrainConfig | null = null

  async init(
    containerId: string,
    brainConfig?: BrainConfig,
    options?: AvatarInitOptions,
  ): Promise<void> {
    this.config = await getAvatarConfig()
    this.brainConfig = brainConfig ?? null

    const container = document.getElementById(containerId)
    if (!container) {
      throw new Error(`Container #${containerId} not found`)
    }

    const agentOptions: Record<string, unknown> = {
      containerId,
      container,
      appId: this.config.appId,
      ...(options?.sessionSpeakReqId !== undefined
        ? { session_speak_req_id: options.sessionSpeakReqId }
        : {}),
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
      "proxyWidget": {
        subtitle_on: (data: any) => {
          this.subtitleCallback?.(data?.text ?? null, true)
        },
        subtitle_off: (_data: any) => {
          this.subtitleCallback?.(null, false)
        },
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
      onMessage: (error: any) => {
        console.error(
          '[Avatar] SDK message:',
          error.error_name || error.code,
          error.message,
        )
      },
      agentCallbacks: {
        onASRResult: (result: any) => {
          if (this.asrCallback) {
            this.asrCallback({ text: result.text, isFinal: result.isFinal })
          }
        },
        onLLMResponse: (event: any) => {
          if (this.llmResponseCallback) {
            const response: AgentLLMResponse = {
              event: event.event,
              ...(typeof event.text === 'string' ? { text: event.text } : {}),
              ...(event.is_first === true ? { isFirst: true } : {}),
              ...(event.usage ? {
                usage: {
                  promptTokens: event.usage.prompt_tokens ?? 0,
                  completionTokens: event.usage.completion_tokens ?? 0,
                  totalTokens: event.usage.total_tokens ?? 0,
                  cachedTokens: event.usage.cached_tokens ?? 0,
                },
              } : {}),
            }
            this.llmResponseCallback(response)
          }
        },
        onAgentStateChange: (state: string) => {
          console.debug('[Avatar] agent state:', state)
        },
        onSpeakStateChange: (event: any) => {
          console.debug('[Avatar] speak state:', event.state)
        },
        onConversationChange: (event: any) => {
          console.debug('[Avatar] conversation:', event.state)
        },
        onError: (error: any) => {
          console.error('[Avatar] error:', error.code, error.message)
        },
      },
    }

    if (this.brainConfig) {
      agentOptions['brain_config'] = {
        provider: this.brainConfig.provider,
        model: this.brainConfig.model,
        api_key: this.brainConfig.api_key,
        base_url: this.brainConfig.base_url,
        ...(this.brainConfig.extra_body ? { extra_body: this.brainConfig.extra_body } : {}),
      }
    }

    this.agent = new XingyunAvatarAgent(agentOptions as any)

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

  /** 停止流式播报：发送空的 is_end 帧关闭当前播报流 */
  stopSpeakStream(): void {
    if (!this.agent) return
    try {
      ; (this.agent as any).sendControl({
        type: 'speak',
        message: { text: '', is_start: false, is_end: true },
      })
    } catch { /* ignore */ }
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

  /** 容器尺寸/位置变化时通知 SDK 重新适配画布，避免销毁重建 */
  resize(): void {
    if (!this.agent) return
    try {
      // SDK 可能暴露 resize 或 updateCanvas 方法，优先调用
      const agent = this.agent as unknown as {
        resize?: () => void
        updateCanvas?: () => void
        onResize?: () => void
      }
      if (typeof agent.resize === 'function') {
        agent.resize()
      } else if (typeof agent.updateCanvas === 'function') {
        agent.updateCanvas()
      } else if (typeof agent.onResize === 'function') {
        agent.onResize()
      }
    } catch (e) {
      console.debug('[Avatar] resize skipped:', e)
    }
  }

  /** 注册字幕显示回调，用于 SDK 代理 subtitle_on / subtitle_off 事件 */
  setOnSubtitle(callback: (text: string | null, on: boolean) => void): void {
    this.subtitleCallback = callback
  }

  /** 注册 LLM 响应回调，用于 SDK onLLMResponse 事件 */
  setOnLLMResponse(callback: (response: AgentLLMResponse) => void): void {
    this.llmResponseCallback = callback
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
