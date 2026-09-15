import type { AgentLLMResponse, ASRResult, BrainConfig, RawWidgetEvent } from '@/types'

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
  /** 进入「聆听」姿态（候选人说话时） */
  listen?(): void
  /** 进入「思考」姿态（LLM 生成 / 判题等空窗期，观感上表现为面试官在斟酌） */
  think?(): void
  /** 进入「交互待机」姿态（等待候选人操作，如写代码） */
  interactiveIdle?(): void
  destroy(): Promise<void>
  isReady(): boolean
  /** 容器尺寸/位置变化时调用，通知底层 SDK 重新适配画布（无需销毁重建） */
  resize?(): void
  /** 设置数字人字幕显示回调：on 为 true 显示字幕，false 隐藏 */
  setOnSubtitle?(callback: (text: string | null, on: boolean) => void): void
  /**
   * 设置 SDK 原生 Widget 事件回调（`show_*` / `widget_*`）。
   *
   * 注意：SDK 内置只渲染了 `widget_pic` 与字幕，其余类型必须由业务侧接管，
   * 否则会被静默丢弃。该回调同时用于探测实际下发的类型名（待验证项 Q7）。
   */
  setOnWidget?(callback: (widget: RawWidgetEvent) => void): void
  /** 设置 LLM 响应回调：SDK 收到 chunk/done 时触发 */
  setOnLLMResponse?(callback: (response: AgentLLMResponse) => void): void
}
