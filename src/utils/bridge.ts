export type HostEnv = 'web' | 'capacitor' | 'miniprogram'

/** 检测当前运行宿主环境 */
export function detectHost(): HostEnv {
  if (typeof (window as any).__wx !== 'undefined') return 'miniprogram'
  if (typeof (window as any).Capacitor !== 'undefined') return 'capacitor'
  return 'web'
}

/** 分享（当前宿主平台可用则调用原生） */
export async function shareContent(opts: {
  title?: string
  text?: string
  url?: string
}): Promise<void> {
  const host = detectHost()
  if (host === 'capacitor') {
    try {
      const { Share } = await import('@capacitor/share')
      await Share.share(opts)
      return
    } catch {
      // Fallback
    }
  }
  // Web fallback
  if (navigator.share) {
    try {
      await navigator.share(opts)
      return
    } catch {
      // 用户取消或不支持
    }
  }
  if (navigator.clipboard && opts.url) {
    await navigator.clipboard.writeText(opts.url)
    alert('链接已复制到剪贴板')
  }
}

/** 请求关闭页面 / 返回上一页 */
export function requestClose(): void {
  const host = detectHost()
  if (host === 'miniprogram' && (window as any).__wx?.miniProgram) {
    ;(window as any).__wx.miniProgram.navigateBack({ delta: 1 })
  } else if (host === 'capacitor') {
    const isAndroid = /Android/i.test(navigator.userAgent)
    if (isAndroid) {
      import('@capacitor/app')
        .then(({ App }) => { App.exitApp() })
        .catch(() => {})
    }
  } else if (window.history.length > 1) {
    window.history.back()
  }
}

/** 宿主→H5 消息映射表 */
type HostMessage = { type: string; payload?: unknown }
const listeners = new Map<string, Set<(payload: unknown) => void>>()

/** 注册宿主消息监听 */
export function onHostMessage(type: string, handler: (payload: unknown) => void): () => void {
  if (!listeners.has(type)) listeners.set(type, new Set())
  listeners.get(type)!.add(handler)
  return () => {
    listeners.get(type)?.delete(handler)
  }
}

/** @internal */
export function dispatchHostMessage(msg: HostMessage): void {
  const set = listeners.get(msg.type)
  if (set) set.forEach((h) => h(msg.payload))
}

/**
 * 小程序 web-view → H5 回调入口
 * 小程序 evalJS 时调用 window.__onMiniMessage({ type, payload })
 */
;(window as any).__onMiniMessage = (msg: HostMessage) => {
  dispatchHostMessage(msg)
}

/**
 * H5 → 小程序 实时触发（通过 URL 参数方案）
 * 小程序在 web-view 加载后，H5 可通过修改 hash 传递动作
 * 小程序侧通过 onLoad/onShow 读取 URL 参数并处理
 */
export function triggerMiniProgramAction(action: string, payload?: Record<string, unknown>): void {
  if (detectHost() !== 'miniprogram') return
  const params = new URLSearchParams()
  params.set('action', action)
  if (payload) params.set('payload', JSON.stringify(payload))
  const newHash = `#/mp-action?${params.toString()}`
  window.location.hash = newHash
}