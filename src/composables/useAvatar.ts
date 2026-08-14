import { ref } from 'vue'
import type { AvatarProvider } from '@/providers/avatarProvider'
import { DigitalAvatarProvider } from '@/providers/digitalAvatarProvider'
import { LottieAvatarProvider } from '@/providers/lottieAvatarProvider'
import { WebSpeechTtsProvider } from '@/providers/webSpeechTtsProvider'
import { WebSpeechAsrProvider } from '@/providers/webSpeechAsrProvider'
import { detectHost } from '@/utils/bridge'
import { useDevice } from '@/composables/useDevice'

const avatarProvider = ref<AvatarProvider | null>(null)
const isDigital = ref(false)

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

export function useAvatar() {
  async function initAvatar(containerId: string): Promise<AvatarProvider> {
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
        const provider = new DigitalAvatarProvider()
        await provider.init(containerId)
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

  return { initAvatar, getProvider, destroyAvatar, isDigital }
}