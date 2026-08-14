import { detectHost } from '@/utils/bridge'

export function useMobile() {
  const host = detectHost()

  async function pickFile(): Promise<File | null> {
    return new Promise((resolve) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.onchange = (e: any) => resolve(e.target.files?.[0] || null)
      input.click()
    })
  }

  return { pickFile, host }
}