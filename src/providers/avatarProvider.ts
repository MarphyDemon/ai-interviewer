import type { ASRResult } from '@/types'

export interface AvatarProvider {
  init(containerId: string): Promise<void>
  speak(text: string): Promise<void>
  /** 流式追加播报：收到增量文本即送播，不中断当前播报（边生成边讲） */
  speakChunk?(text: string): void
  /** 开始一轮流式播报会话（重置 is_start 状态） */
  startSpeakStream?(): void
  /** 结束本轮流式播报：发送最后一帧（is_end=true，可携带剩余文本） */
  endSpeakStream?(text: string): void
  startASR(onResult: (result: ASRResult) => void): Promise<void>
  stopASR(): Promise<void>
  interrupt(): Promise<void>
  idle(): void
  destroy(): Promise<void>
  isReady(): boolean
}
