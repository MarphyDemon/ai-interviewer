import { detectHost, shareContent } from '@/utils/bridge'

export function useMobile() {
  const host = detectHost()
  const isCapacitor = host === 'capacitor'
  const isMiniprogram = host === 'miniprogram'

  async function pickFile(): Promise<File | null> {
    return new Promise((resolve) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.onchange = (e: any) => resolve(e.target.files?.[0] || null)
      input.click()
    })
  }

  async function share(opts: { title?: string; text?: string; url?: string }): Promise<void> {
    await shareContent(opts)
  }

  return { pickFile, share, host, isCapacitor, isMiniprogram }
}
