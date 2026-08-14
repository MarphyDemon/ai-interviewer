import { ref, computed, onMounted, onUnmounted } from 'vue'

const MOBILE_BREAKPOINT = 768

export function useDevice() {
  const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024)
  const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 768)
  const userAgent = ref(typeof navigator !== 'undefined' ? navigator.userAgent : '')

  const isMobile = computed(() => {
    return (
      windowWidth.value < MOBILE_BREAKPOINT ||
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        userAgent.value
      )
    )
  })

  const isIOS = computed(() => /iPhone|iPad|iPod/i.test(userAgent.value))
  const isAndroid = computed(() => /Android/i.test(userAgent.value))
  const isTouch = computed(() => {
    if (typeof window === 'undefined') return false
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0
  })
  const isLandscape = computed(() => windowWidth.value > windowHeight.value)

  const handleResize = () => {
    windowWidth.value = window.innerWidth
    windowHeight.value = window.innerHeight
  }

  onMounted(() => {
    window.addEventListener('resize', handleResize)
    window.addEventListener('orientationchange', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    window.removeEventListener('orientationchange', handleResize)
  })

  return { isMobile, isIOS, isAndroid, isTouch, isLandscape, windowWidth, windowHeight }
}