import { ref } from 'vue'
import type { AvatarProvider, AvatarInitOptions } from '@/providers/avatarProvider'
import { DigitalAvatarProvider } from '@/providers/digitalAvatarProvider'
import { LottieAvatarProvider } from '@/providers/lottieAvatarProvider'
import { WebSpeechTtsProvider } from '@/providers/webSpeechTtsProvider'
import { WebSpeechAsrProvider } from '@/providers/webSpeechAsrProvider'
import { detectHost } from '@/utils/bridge'
import { useDevice } from '@/composables/useDevice'
import { getBrainConfig } from '@/api/avatar'
import type { BrainConfig } from '@/types'

const avatarProvider = ref<AvatarProvider | null>(null)
const isDigital = ref(false)
const lastBrainConfig = ref<BrainConfig | null>(null)

function supportsWebGL2(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('experimental-webgl2'))
  } catch {
    return false
  }
}

function supportsWebCodecs(): boolean {
  return typeof window !== 'undefined' && 'VideoDecoder' in window
}

export interface InitAvatarOptions extends AvatarInitOptions {
  /** 聊天场景：绑定到已有会话（不传则新建） */
  conversationId?: number
  /**
   * 面试场景：由面试链路签发的 brain_config。
   * 传入时直接使用，不再请求 /avatar/brain-config（避免落到聊天链路的学习导师）。
   */
  brainConfig?: BrainConfig
}

export function useAvatar() {
  async function initAvatar(
    containerId: string,
    options: number | InitAvatarOptions = {},
  ): Promise<AvatarProvider> {
    // 兼容旧签名 initAvatar(containerId, conversationId?: number)
    const opts: InitAvatarOptions =
      typeof options === 'number' ? { conversationId: options } : options

    const host = detectHost()
    const { isMobile } = useDevice()

    // Mini program: force Lottie (WebGL not supported)
    if (host === 'miniprogram') {
      return createLottieProvider(containerId)
    }

    // Mobile: try WebGL first, fallback to Lottie
    // Desktop: try WebGL + WebCodecs, fallback to Lottie
    const webglOk = supportsWebGL2()
    const webCodecsOk = supportsWebCodecs()

    if (webglOk && (isMobile.value || webCodecsOk)) {
      try {
        let brainConfig: BrainConfig | undefined = opts.brainConfig
        if (brainConfig) {
          lastBrainConfig.value = brainConfig
        } else {
          try {
            brainConfig = await getBrainConfig(opts.conversationId)
            lastBrainConfig.value = brainConfig ?? null
          } catch {
            console.warn('[Avatar] Failed to fetch brain-config, SDK will use default behavior')
          }
        }
        const provider = new DigitalAvatarProvider()
        await provider.init(containerId, brainConfig, opts)
        avatarProvider.value = provider
        isDigital.value = true
        return provider
      } catch (e) {
        console.warn('[Avatar] Digital avatar init failed, falling back to Lottie:', e)
      }
    }

    return createLottieProvider(containerId)
  }

  function createLottieProvider(containerId: string): AvatarProvider {
    const tts = new WebSpeechTtsProvider()
    const asr = new WebSpeechAsrProvider()
    const provider = new LottieAvatarProvider(tts, asr)
    provider.init(containerId)
    avatarProvider.value = provider
    isDigital.value = false
    return provider
  }

  function getProvider(): AvatarProvider | null {
    return avatarProvider.value
  }

  async function destroyAvatar(): Promise<void> {
    if (avatarProvider.value) {
      await avatarProvider.value.destroy()
      avatarProvider.value = null
    }
  }

  return { initAvatar, getProvider, destroyAvatar, isDigital, lastBrainConfig }
}