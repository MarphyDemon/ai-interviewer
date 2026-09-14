import type { AgentLLMResponse, ASRResult, BrainConfig } from '@/types'

/** 数字人初始化可选项 */
export interface AvatarInitOptions {
  /**
   * Agent 会话播报序号起始值：
   * - 1（默认）：会话开始即触发一轮播报（SDK 生成开场白）
   * - 0：无开场白，等业务侧显式播报
   *
   * 面试场景传 0 —— 开场白由面试编排给出，避免与 SDK 自动开场重复。
   */
  sessionSpeakReqId?: 0 | 1
}

export interface AvatarProvider {
  init(containerId: string, brainConfig?: BrainConfig, options?: AvatarInitOptions): Promise<void>
  speak(text: string): Promise<void>
  /** 流式追加播报：收到增量文本即送播，不中断当前播报（边生成边讲） */
  speakChunk?(text: string): void
  /** 开始一轮流式播报会话（重置 is_start 状态） */
  startSpeakStream?(): void
  /** 结束本轮流式播报：发送最后一帧（is_end=true，可携带剩余文本） */
  endSpeakStream?(text: string): void
  /** 停止流式播报：立即中断当前正在播放的语音 */
  stopSpeakStream?(): void
  startASR(onResult: (result: ASRResult) => void): Promise<void>
  stopASR(): Promise<void>
  interrupt(): Promise<void>
  idle(): void
  destroy(): Promise<void>
  isReady(): boolean
  /** 容器尺寸/位置变化时调用，通知底层 SDK 重新适配画布（无需销毁重建） */
  resize?(): void
  /** 设置数字人字幕显示回调：on 为 true 显示字幕，false 隐藏 */
  setOnSubtitle?(callback: (text: string | null, on: boolean) => void): void
  /** 设置 LLM 响应回调：SDK 收到 chunk/done 时触发 */
  setOnLLMResponse?(callback: (response: AgentLLMResponse) => void): void
}
